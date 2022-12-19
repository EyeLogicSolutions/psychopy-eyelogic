import webbrowser

import requests
import wx
import sys
import subprocess as sp
from pypi_search import search as pypi

from psychopy.app import utils
from psychopy.app.themes import handlers, icons
from psychopy.localization import _translate
from psychopy.tools import filetools as ft

from psychopy.tools.pkgtools import getInstalledPackages, getPackageMetadata, getPypiInfo, isInstalled


def installPackage(name, version=None):
    # Append version if given
    if version is not None:
        name += f"=={version}"
    # Attempt to install
    emts = [sys.executable, "-m pip install", name]
    output = sp.Popen(' '.join(emts),
                      stdout=sp.PIPE,
                      stderr=sp.PIPE,
                      shell=True,
                      universal_newlines=True)
    stdout, stderr = output.communicate()
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)

    if output.returncode != 0:
        # Display output if error
        cmd = "\n>> pip install" + name + "\n"
        dlg = InstallErrorDlg(
            cmd=cmd,
            stdout=stdout,
            stderr=stderr,
            label=_translate("Package {} could not be installed.").format(name)
        )
    else:
        # Display success message if success
        dlg = wx.MessageDialog(
            parent=None,
            caption=_translate("Package installed"),
            message=_translate("Package {} successfully installed!").format(name),
            style=wx.ICON_INFORMATION
        )
    dlg.ShowModal()


def uninstallPackage(name):
    # Attempt to uninstall
    emts = [sys.executable, "-m pip uninstall", name]
    output = sp.Popen(' '.join(emts),
                      stdout=sp.PIPE,
                      stderr=sp.PIPE,
                      shell=True,
                      universal_newlines=True)
    stdout, stderr = output.communicate()
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)

    if output.returncode != 0:
        # Display output if error
        cmd = "\n>> pip uninstall" + name + "\n"
        dlg = InstallErrorDlg(
            cmd=cmd,
            stdout=stdout,
            stderr=stderr,
            label=_translate("Package {} could not be uninstalled.").format(name)
        )
    else:
        # Display success message if success
        dlg = wx.MessageDialog(
            parent=None,
            caption=_translate("Package uninstalled"),
            message=_translate("Package {} successfully uninstalled!").format(name),
            style=wx.ICON_INFORMATION
        )
    dlg.ShowModal()


class InstallErrorDlg(wx.Dialog, handlers.ThemeMixin):
    def __init__(self, label, caption=_translate("PIP error"), cmd="", stdout="", stderr=""):
        from psychopy.app.themes import fonts
        # Initialise
        wx.Dialog.__init__(
            self, None,
            size=(480, 620),
            title=caption,
            style=wx.RESIZE_BORDER | wx.CLOSE_BOX | wx.CAPTION
        )
        # Setup sizer
        self.border = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.border)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.border.Add(self.sizer, proportion=1, border=6, flag=wx.ALL | wx.EXPAND)
        # Create title sizer
        self.title = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.title, border=6, flag=wx.ALL | wx.EXPAND)
        # Create icon
        self.icon = wx.StaticBitmap(
            self, size=(32, 32),
            bitmap=icons.ButtonIcon(stem="stop", size=32).bitmap
        )
        self.title.Add(self.icon, border=6, flag=wx.ALL | wx.EXPAND)
        # Create title
        self.titleLbl = wx.StaticText(self, label=label)
        self.titleLbl.SetFont(fonts.appTheme['h3'].obj)
        self.title.Add(self.titleLbl, proportion=1, border=6, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        # Show what we tried
        self.inLbl = wx.StaticText(self, label=_translate("We tried:"))
        self.sizer.Add(self.inLbl, border=6, flag=wx.ALL | wx.EXPAND)
        self.inCtrl = wx.TextCtrl(self, value=cmd, style=wx.TE_READONLY)
        self.inCtrl.SetBackgroundColour("white")
        self.inCtrl.SetFont(fonts.appTheme['code'].obj)
        self.sizer.Add(self.inCtrl, border=6, flag=wx.ALL | wx.EXPAND)
        # Show what we got
        self.outLbl = wx.StaticText(self, label=_translate("We got:"))
        self.sizer.Add(self.outLbl, border=6, flag=wx.ALL | wx.EXPAND)
        self.outCtrl = wx.TextCtrl(self, value=f"{stdout}\n{stderr}",
                                   size=(-1, 620), style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.outCtrl.SetFont(fonts.appTheme['code'].obj)
        self.sizer.Add(self.outCtrl, proportion=1, border=6, flag=wx.ALL | wx.EXPAND)

        # Make buttons
        self.btns = self.CreateStdDialogButtonSizer(flags=wx.OK)
        self.border.Add(self.btns, border=6, flag=wx.ALIGN_RIGHT | wx.ALL)

        self.Layout()
        self._applyAppTheme()

    def ShowModal(self):
        # Make error noise
        wx.Bell()
        # Show as normal
        wx.Dialog.ShowModal(self)


class PackageManagerPanel(wx.Panel, handlers.ThemeMixin):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        # Setup sizer
        self.border = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.border)
        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.border.Add(self.sizer, proportion=1, border=6, flag=wx.ALL | wx.EXPAND)
        # Add package list
        self.packageList = PackageListCtrl(self)
        self.packageList.Bind(wx.EVT_LIST_ITEM_SELECTED, self.onSelectItem)
        self.sizer.Add(self.packageList, flag=wx.EXPAND | wx.ALL)
        # Seperator
        self.sizer.Add(wx.StaticLine(self, style=wx.LI_VERTICAL), border=6, flag=wx.EXPAND | wx.ALL)
        # Add details panel
        self.detailsPanel = PackageDetailsPanel(self)
        self.sizer.Add(self.detailsPanel, proportion=1, flag=wx.EXPAND | wx.ALL)

    def onSelectItem(self, evt=None):
        # Get package name
        pipname = evt.GetText()
        # Set pip details from name
        self.detailsPanel.package = pipname


class PIPTerminalPanel(wx.Panel):
    """
    Interface for interacting with PIP within the standalone PsychoPy environment.
    """

    def __init__(self, parent):
        wx.Panel.__init__(self, parent)

        # Setup sizers
        self.border = wx.BoxSizer()
        self.SetSizer(self.border)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.border.Add(self.sizer, proportion=1, border=12, flag=wx.ALL | wx.EXPAND)

        # Add output
        self.output = wx.richtext.RichTextCtrl(
            self,
            value=_translate(
                "Type a PIP command below and press Enter to execute it in the installed PsychoPy environment, any "
                "returned text will appear below.\n"
                "\n"
            ),
            size=(480, -1),
            style=wx.TE_READONLY)
        self.sizer.Add(self.output, proportion=1, border=6, flag=wx.ALL | wx.EXPAND)

        # Add text control
        self.consoleSzr = wx.BoxSizer(wx.HORIZONTAL)
        self.consoleLbl = wx.StaticText(self, label=">>")
        self.consoleSzr.Add(self.consoleLbl, border=6, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.console = wx.TextCtrl(self, size=(-1, -1), style=wx.TE_PROCESS_ENTER)
        self.console.Bind(wx.EVT_TEXT_ENTER, self.onEnter)
        self.consoleSzr.Add(self.console, proportion=1)
        self.sizer.Add(self.consoleSzr, border=6, flag=wx.ALL | wx.EXPAND)

        self._applyAppTheme()

        self.Center()

    def onEnter(self, evt=None):
        # Get current command
        cmd = self.console.GetValue()
        # Clear text entry
        self.console.Clear()
        # Run command
        self.runCommand(cmd)

    def runCommand(self, cmd):
        """Run the command."""
        emts = [sys.executable, "-m", cmd]
        output = sp.Popen(' '.join(emts),
                          stdout=sp.PIPE,
                          stderr=sp.PIPE,
                          shell=True,
                          universal_newlines=True)
        stdout, stderr = output.communicate()
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)

        # Display input
        self.output.AppendText("\n>> " + cmd + "\n")

        # Display output if error
        if output.returncode != 0:
            self.output.AppendText(stderr)

        self.output.AppendText(stdout)

        # Update output ctrl to style new text
        handlers.ThemeMixin._applyAppTheme(self.output)

        # Scroll to bottom
        self.output.ShowPosition(self.output.GetLastPosition())

    def _applyAppTheme(self):
        # Style output ctrl
        handlers.ThemeMixin._applyAppTheme(self.output)
        # Apply code font to text ctrl
        from psychopy.app.themes import fonts
        self.console.SetFont(fonts.coderTheme.base.obj)


class PackageListCtrl(wx.Panel, handlers.ThemeMixin):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, size=(300, -1))
        # Setup sizers
        self.border = wx.BoxSizer()
        self.SetSizer(self.border)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.border.Add(self.sizer, proportion=1, border=12, flag=wx.ALL | wx.EXPAND)

        # Search bar
        self.searchCtrl = wx.SearchCtrl(self)
        self.searchCtrl.Bind(wx.EVT_SEARCH, self.refresh)
        self.sizer.Add(self.searchCtrl, border=6, flag=wx.ALL | wx.EXPAND)
        # Create list ctrl
        self.ctrl = utils.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.ctrl.setResizeColumn(0)
        self.ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.onItemSelected)
        self.ctrl.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.onRightClick)
        self.sizer.Add(self.ctrl, proportion=1, border=6, flag=wx.LEFT | wx.RIGHT | wx.EXPAND)

        # "Or..." label
        self.orLbl = wx.StaticText(self, label=_translate("or..."))
        self.sizer.Add(self.orLbl, border=3, flag=wx.ALL | wx.ALIGN_CENTER)
        # Add by file...
        self.addFileBtn = utils.HoverButton(self, label=_translate("Install from file"))
        self.addFileBtn.SetToolTipString(_translate("Install a package from a local file, such as a .egg or wheel."))
        self.addFileBtn.Bind(wx.EVT_BUTTON, self.onAddFromFile)
        self.sizer.Add(self.addFileBtn, border=6, flag=wx.ALL | wx.ALIGN_CENTER)
        # Add button to open pip
        self.terminalBtn = utils.HoverButton(self, label=_translate("Open PIP terminal"))
        self.terminalBtn.SetToolTipString(_translate("Open PIP terminal to manage packages manually"))
        self.sizer.Add(self.terminalBtn, border=3, flag=wx.ALL | wx.ALIGN_CENTER)
        self.terminalBtn.Bind(wx.EVT_BUTTON, self.onOpenPipTerminal)

        # Initial data
        self.refresh()

        self.Layout()
        self._applyAppTheme()

    def _applyAppTheme(self):
        return

    def onOpenPipTerminal(self, evt=None):
        # Make dialog
        dlg = wx.Dialog(self, title="PIP Terminal", size=(480, 480), style=wx.RESIZE_BORDER | wx.CAPTION | wx.CLOSE_BOX)
        # Setup sizer
        dlg.sizer = wx.BoxSizer(wx.VERTICAL)
        dlg.SetSizer(dlg.sizer)
        # Add panel
        panel = PIPTerminalPanel(dlg)
        dlg.sizer.Add(panel, proportion=1, border=6, flag=wx.ALL | wx.EXPAND)
        # Layout
        dlg.Layout()
        # Show
        dlg.Show()

    def onItemSelected(self, evt=None):
        # Post event so it can be caught by parent
        evt.SetEventObject(self)
        wx.PostEvent(self, evt)

    def onRightClick(self, evt=None):
        # Create menu
        menu = wx.Menu()
        # Map menu functions
        menu.functions = {}
        if isInstalled(evt.GetText()):
            # Add uninstall if installed
            uninstallOpt = menu.Append(wx.ID_ANY, item=_translate("Uninstall"))
            menu.functions[uninstallOpt.GetId()] = self.onUninstall
        else:
            # Add install if not installed
            uninstallOpt = menu.Append(wx.ID_ANY, item=_translate("Install"))
            menu.functions[uninstallOpt.GetId()] = self.onInstall
        # Bind choice event
        menu.Bind(wx.EVT_MENU, self.onRightClickMenuChoice)
        # Store pip name as attribute of menu
        menu.pipname = evt.GetText()
        # Show menu
        self.PopupMenu(menu)

    def onRightClickMenuChoice(self, evt=None):
        # Work out what was chosen
        menu = evt.GetEventObject()
        choice = evt.GetId()
        if choice not in menu.functions:
            return
        # Perform associated method
        menu.functions[choice](evt)

    def onUninstall(self, evt=None):
        # Get rightclick menu
        menu = evt.GetEventObject()
        pipname = menu.pipname
        msg = wx.MessageDialog(
            self,
            "Are you sure you want to uninstall package `{}`?".format(pipname),
            caption="Uninstall Package?",
            style=wx.YES_NO | wx.NO_DEFAULT)

        # if user selects NO, exit the routine
        if msg.ShowModal() == wx.ID_YES:
            uninstallPackage(pipname)
            self.refresh()

    def onInstall(self, evt=None):
        # Get rightclick menu
        menu = evt.GetEventObject()
        pipname = menu.pipname
        # Install package
        installPackage(pipname)
        self.refresh()

    def refresh(self, evt=None):
        # Get search term
        searchTerm = self.searchCtrl.GetValue()
        # Clear
        self.ctrl.ClearAll()
        self.ctrl.AppendColumn(_translate("Package"))
        self.ctrl.AppendColumn(_translate("Installed"))

        # Get installed packages
        installedPackages = dict(getInstalledPackages())
        # If there's no search term, show all installed and return
        if searchTerm in (None, ""):
            for pkg, version in installedPackages.items():
                item = self.ctrl.Append((pkg, version))
                self.ctrl.SetItemFont(item, font=wx.Font().Bold())
            return
        # Add column for latest version if we're actually searching
        self.ctrl.AppendColumn(_translate("Latest"))
        # Get packages from search
        foundPackages = pypi.find_packages(self.searchCtrl.GetValue())
        # Populate
        for pkg in foundPackages:
            font = wx.Font()
            if pkg['name'] in installedPackages:
                # If installed, add row with value for installed version
                item = self.ctrl.Append((pkg['name'], installedPackages[pkg['name']], pkg['version']))
                font = font.Bold()
            else:
                # Otherwise, add row with installed version blank
                item = self.ctrl.Append((pkg['name'], "-", pkg['version']))
            # Style new row according to install status
            self.ctrl.SetItemFont(item, font)

    def onAddFromFile(self, evt=None):
        # Create dialog to get package file location
        dlg = wx.FileDialog(
            self,
            wildcard="Wheel files (.whl)|.whl|Source distribution files (.sdist)|.sdist",
            style=wx.FD_OPEN | wx.FD_SHOW_HIDDEN)
        if dlg.ShowModal() == wx.ID_OK:
            # Install
            installPackage(dlg.GetPath())
            # Reload packages
            self.refresh()

    def execute(self, params):
        """
        Execute a pip command

        Parameters
        ----------
        params : str or list
            Pip command params (everything after the word `pip`)
        """
        if not isinstance(params, str):
            params = " ".join(params)
        # Construct pip command
        cmd = f"{sys.executable} -m pip {params}"
        # Send to console
        output = sp.Popen(cmd,
                          stdout=sp.PIPE,
                          stderr=sp.PIPE,
                          shell=True,
                          universal_newlines=True)
        stdout, stderr = output.communicate()
        # Show error dialog if something went wrong
        if stderr:
            mode = params.split(" ")[0]
            dlg = InstallErrorDlg(
                cmd=cmd,
                stdout=stdout,
                stderr=stderr,
                label=_translate("Failed to {} package").format(mode))
            dlg.ShowModal()
        else:
            dlg = wx.MessageDialog(
                self,
                message=_translate("Successfully completed: `pip {}`").format(params),
                style=wx.ICON_INFORMATION
            )
            dlg.ShowModal()
        # Refresh packages list
        self.refresh()


class PackageDetailsPanel(wx.Panel, handlers.ThemeMixin):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        # Setup sizers
        self.border = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.border)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.border.Add(self.sizer, proportion=1, border=12, flag=wx.ALL | wx.EXPAND)

        # Name sizer
        self.nameSzr = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.nameSzr)
        # Name
        self.nameCtrl = wx.StaticText(self)
        self.nameSzr.Add(self.nameCtrl, border=6, flag=wx.TOP | wx.LEFT | wx.RIGHT | wx.EXPAND)
        # Author
        self.authorSzr = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.authorSzr, border=6, flag=wx.BOTTOM | wx.LEFT | wx.RIGHT | wx.EXPAND)
        self.authorPre = wx.StaticText(self, label=_translate("by "))
        self.authorSzr.Add(self.authorPre, border=0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        self.authorCtrl = utils.HyperLinkCtrl(self)
        self.authorSzr.Add(self.authorCtrl, border=0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        self.licenseCtrl = wx.StaticText(self)
        self.authorSzr.Add(self.licenseCtrl, border=0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        # Header buttons sizer
        self.headBtnSzr = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.headBtnSzr, border=3, flag=wx.ALL | wx.EXPAND)
        # Homepage button
        self.homeBtn = wx.Button(self, label=_translate("Homepage"))
        self.headBtnSzr.Add(self.homeBtn, border=3, flag=wx.ALL | wx.EXPAND)
        self.homeBtn.Bind(wx.EVT_BUTTON, self.onHomepage)
        # Install button
        self.installBtn = wx.Button(self, label=_translate("Install"))
        self.headBtnSzr.Add(wx.StaticLine(self, style=wx.LI_VERTICAL), border=6, flag=wx.LEFT | wx.RIGHT | wx.EXPAND)
        self.headBtnSzr.Add(self.installBtn, border=3, flag=wx.ALL | wx.EXPAND)
        self.installBtn.Bind(wx.EVT_BUTTON, self.onInstall)
        # Version chooser
        self.versionCtrl = wx.Choice(self)
        self.headBtnSzr.Add(self.versionCtrl, border=3, flag=wx.RIGHT | wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER)
        self.versionCtrl.Bind(wx.EVT_CHOICE, self.onVersion)
        # Description
        self.descCtrl = utils.MarkdownCtrl(self, style=wx.TE_READONLY | wx.TE_MULTILINE | wx.BORDER_NONE | wx.TE_NO_VSCROLL)
        self.sizer.Add(self.descCtrl, proportion=1, border=6, flag=wx.ALL | wx.EXPAND)
        # todo: Required by...

        self.package = None

    @property
    def package(self):
        if hasattr(self, "_package"):
            return self._package

    @package.setter
    def package(self, pipname):
        self._package = pipname

        # Disable/enable according to whether None
        active = pipname is not None
        self.homeBtn.Enable(active)
        self.installBtn.Enable(active)
        self.nameCtrl.Enable(active)
        self.versionCtrl.Enable(active)
        self.authorPre.Enable(active)
        self.authorCtrl.Enable(active)
        self.licenseCtrl.Enable(active)
        self.descCtrl.Enable(active)

        if self._package is None:
            # Show placeholder text
            self.params = {
                "name": "...",
                "author": "...",
                "authorEmail": "",
                "license": "",
                "summary": "",
                "desc": "",
                'version': None,
                'releases': []
            }
        else:
            # Get data from pypi
            pypiData = getPypiInfo(self._package)
            # Get package metadata (if installed)
            if self._package in dict(getInstalledPackages()):
                metadata = getPackageMetadata(self._package)
            else:
                metadata = {}
            # Get best data available, prioritising local metadata
            self.params = {
                'name': metadata.get('Name', pypiData.get('Name', pipname)),
                'author': metadata.get('Author', pypiData.get('author', 'Unknown')),
                'authorEmail': metadata.get('Author-email', pypiData.get('author_email', 'Unknown')),
                'license': metadata.get('License', pypiData.get('license', 'Unknown')),
                'summary': metadata.get('Summary', pypiData.get('summary', '')),
                'desc': metadata.get('Description', pypiData.get('description', '')),
                'version': metadata.get('Version', None),
                'releases': pypiData.get('Releases', pypiData.get('releases', []))
            }

        # Set values from params
        self.nameCtrl.SetLabelText(self.params['name'])
        self.authorCtrl.SetLabel(self.params['author'])
        self.authorCtrl.URL = "mailto:" + self.params['authorEmail']
        self.authorCtrl.SetToolTip(self.params['authorEmail'])
        self.licenseCtrl.SetLabelText(" (License: %(license)s)" % self.params)
        self.descCtrl.setValue("%(summary)s\n\n%(desc)s" % self.params)
        # Set current and possible versions
        self.versionCtrl.Clear()
        self.versionCtrl.AppendItems(self.params['releases'])
        if self.params['version'] is None:
            self.versionCtrl.SetSelection(0)
        else:
            if self.params['version'] not in self.versionCtrl.GetStrings():
                self.versionCtrl.Append(self.params['version'])
            self.versionCtrl.SetStringSelection(self.params['version'])
        self.onVersion()

        self.Layout()
        self._applyAppTheme()

    def onHomepage(self, evt=None):
        # Open homepage in browser
        webbrowser.open(self.params.get('Home-page'))

    def onLocalDir(self, evt=None):
        # Get local dir from pip
        output = sp.Popen(f"{sys.executable} -m pip show {self.package}",
                          stdout=sp.PIPE,
                          stderr=sp.PIPE,
                          shell=True,
                          universal_newlines=True)
        stdout, stderr = output.communicate()
        # Show error dialog if something went wrong
        if stderr:
            dlg = InstallErrorDlg(
                cmd=f">> pip show {self.package}",
                stdout=stdout,
                stderr=stderr,
                label=_translate("Could not find local directory for package {}").format(self.package))
            dlg.ShowModal()
        else:
            # Open local director via default file browser
            lines = stdout.split("\n")
            for line in lines:
                line = line.split(":", 1)
                if line[0] == "Location":
                    ft.openInExplorer(line[1])
                    break

    def onInstall(self, evt=None):
        # Install package then disable the button to indicate it's installed
        installPackage(self.package, version=self.versionCtrl.GetStringSelection())
        self.installBtn.Disable()

    def onVersion(self, evt=None):
        # When version selected, enable the install button if the version is different than installed
        self.installBtn.Enable(
            self.versionCtrl.GetStringSelection() != self.params['version'] and self.package is not None
        )

    def _applyAppTheme(self):
        from psychopy.app.themes import fonts
        self.nameCtrl.SetFont(fonts.appTheme['h1'].obj)
        self.installBtn.SetBitmap(icons.ButtonIcon(stem="download", size=16).bitmap)
        self.authorCtrl.SetBackgroundColour("white")


if __name__ == "__main__":
    pass

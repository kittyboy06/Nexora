using System;
using System.Runtime.InteropServices;
using Microsoft.UI.Xaml;

namespace Nexora.Desktop.Services;

public class TrayIconService : IDisposable
{
    private const int WM_USER = 0x0400;
    private const int WM_TRAYICON = WM_USER + 1;
    private const int WM_LBUTTONUP = 0x0202;
    private const int WM_RBUTTONUP = 0x0205;
    private const uint WM_NCDESTROY = 0x0082;

    private const uint NIM_ADD = 0x00000000;
    private const uint NIM_MODIFY = 0x00000001;
    private const uint NIM_DELETE = 0x00000002;

    private const uint NIF_MESSAGE = 0x00000001;
    private const uint NIF_ICON = 0x00000002;
    private const uint NIF_TIP = 0x00000004;

    private const uint MF_STRING = 0x00000000;
    private const uint MF_SEPARATOR = 0x00000800;
    private const uint TPM_RETURNCMD = 0x0100;

    private const int CMD_OPEN_DASHBOARD = 1001;
    private const int CMD_OPEN_COMPANION = 1002;
    private const int CMD_EXIT = 1003;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct NOTIFYICONDATA
    {
        public int cbSize;
        public IntPtr hWnd;
        public int uID;
        public uint uFlags;
        public int uCallbackMessage;
        public IntPtr hIcon;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
        public string szTip;
        public int dwState;
        public int dwStateMask;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)]
        public string szInfo;
        public int uVersionOrTimeout;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)]
        public string szInfoTitle;
        public int dwInfoFlags;
        public Guid guidItem;
        public IntPtr hBalloonIcon;
    }

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    private static extern bool Shell_NotifyIcon(uint dwMessage, ref NOTIFYICONDATA lpData);

    [DllImport("user32.dll")]
    private static extern IntPtr LoadIcon(IntPtr hInstance, IntPtr lpIconName);

    [DllImport("user32.dll")]
    private static extern IntPtr CreatePopupMenu();

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern bool AppendMenu(IntPtr hMenu, uint uFlags, IntPtr uIDNewItem, string lpNewItem);

    [DllImport("user32.dll")]
    private static extern int TrackPopupMenuEx(IntPtr hMenu, uint uFlags, int x, int y, IntPtr hWnd, IntPtr lptpm);

    [DllImport("user32.dll")]
    private static extern bool GetCursorPos(out POINT lpPoint);

    [DllImport("user32.dll")]
    private static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern bool DestroyMenu(IntPtr hMenu);

    private delegate IntPtr SubclassProc(IntPtr hWnd, uint message, IntPtr wParam, IntPtr lParam, UIntPtr uIdSubclass, UIntPtr dwRefData);

    [DllImport("comctl32.dll", SetLastError = true)]
    private static extern bool SetWindowSubclass(IntPtr hWnd, SubclassProc procedure, UIntPtr subclassId, UIntPtr referenceData);

    [DllImport("comctl32.dll", SetLastError = true)]
    private static extern bool RemoveWindowSubclass(IntPtr hWnd, SubclassProc procedure, UIntPtr subclassId);

    [DllImport("comctl32.dll")]
    private static extern IntPtr DefSubclassProc(IntPtr hWnd, uint message, IntPtr wParam, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential)]
    private struct POINT
    {
        public int X;
        public int Y;
    }

    private readonly Window _mainWindow;
    private readonly Action _onShowCompanion;
    private readonly Action _onExit;
    private IntPtr _hwnd;
    private bool _isCreated;
    private bool _isSubclassed;
    private readonly SubclassProc _subclassProc;

    public TrayIconService(Window mainWindow, Action onShowCompanion, Action onExit)
    {
        _mainWindow = mainWindow ?? throw new ArgumentNullException(nameof(mainWindow));
        _onShowCompanion = onShowCompanion ?? throw new ArgumentNullException(nameof(onShowCompanion));
        _onExit = onExit ?? throw new ArgumentNullException(nameof(onExit));
        _subclassProc = WindowProcedure;
    }

    public void Initialize()
    {
        _hwnd = WinRT.Interop.WindowNative.GetWindowHandle(_mainWindow);
        _isSubclassed = SetWindowSubclass(_hwnd, _subclassProc, UIntPtr.One, UIntPtr.Zero);

        var data = new NOTIFYICONDATA
        {
            cbSize = Marshal.SizeOf<NOTIFYICONDATA>(),
            hWnd = _hwnd,
            uID = 1,
            uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP,
            uCallbackMessage = WM_TRAYICON,
            hIcon = LoadIcon(IntPtr.Zero, (IntPtr)32512), // IDI_APPLICATION
            szTip = "NEXORA Desktop Control Plane"
        };

        _isCreated = Shell_NotifyIcon(NIM_ADD, ref data);
    }

    private IntPtr WindowProcedure(IntPtr hWnd, uint message, IntPtr wParam, IntPtr lParam, UIntPtr subclassId, UIntPtr referenceData)
    {
        if (message == WM_TRAYICON)
        {
            var mouseMessage = lParam.ToInt32();
            if (mouseMessage == WM_LBUTTONUP)
            {
                _mainWindow.Activate();
            }
            else if (mouseMessage == WM_RBUTTONUP)
            {
                HandleTrayMenu();
            }
        }

        if (message == WM_NCDESTROY)
        {
            _isSubclassed = false;
        }

        return DefSubclassProc(hWnd, message, wParam, lParam);
    }

    public void HandleTrayMenu()
    {
        if (_hwnd == IntPtr.Zero) return;

        var hMenu = CreatePopupMenu();
        try
        {
            AppendMenu(hMenu, MF_STRING, (IntPtr)CMD_OPEN_DASHBOARD, "Open Dashboard");
            AppendMenu(hMenu, MF_STRING, (IntPtr)CMD_OPEN_COMPANION, "Show Companion");
            AppendMenu(hMenu, MF_SEPARATOR, IntPtr.Zero, string.Empty);
            AppendMenu(hMenu, MF_STRING, (IntPtr)CMD_EXIT, "Exit NEXORA");

            GetCursorPos(out var pt);
            SetForegroundWindow(_hwnd);

            var cmd = TrackPopupMenuEx(hMenu, TPM_RETURNCMD, pt.X, pt.Y, _hwnd, IntPtr.Zero);
            switch (cmd)
            {
                case CMD_OPEN_DASHBOARD:
                    _mainWindow.Activate();
                    break;
                case CMD_OPEN_COMPANION:
                    _onShowCompanion();
                    break;
                case CMD_EXIT:
                    _onExit();
                    break;
            }
        }
        finally
        {
            DestroyMenu(hMenu);
        }
    }

    public void Dispose()
    {
        if (_isSubclassed && _hwnd != IntPtr.Zero)
        {
            RemoveWindowSubclass(_hwnd, _subclassProc, UIntPtr.One);
            _isSubclassed = false;
        }
        if (_isCreated && _hwnd != IntPtr.Zero)
        {
            var data = new NOTIFYICONDATA
            {
                cbSize = Marshal.SizeOf<NOTIFYICONDATA>(),
                hWnd = _hwnd,
                uID = 1
            };
            Shell_NotifyIcon(NIM_DELETE, ref data);
            _isCreated = false;
        }
    }
}

using System;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Nexora.Desktop.ViewModels;
using Windows.Graphics;

namespace Nexora.Desktop.Views;

public sealed partial class CompanionWindow : Window
{
    public MainViewModel ViewModel { get; }

    public CompanionWindow(MainViewModel viewModel)
    {
        ViewModel = viewModel ?? throw new ArgumentNullException(nameof(viewModel));
        this.InitializeComponent();

        if (Content is FrameworkElement root)
        {
            root.DataContext = ViewModel;
        }

        Title = "NEXORA Companion";
        ConfigurePresenterAndPosition();

        OpenDashboardButton.Click += (s, e) => OpenDashboard();
        FooterDashboardButton.Click += (s, e) => OpenDashboard();
    }

    private void ConfigurePresenterAndPosition()
    {
        var presenter = AppWindow.Presenter as OverlappedPresenter;
        if (presenter != null)
        {
            presenter.IsAlwaysOnTop = true;
            presenter.IsResizable = false;
        }

        var displayArea = DisplayArea.GetFromWindowId(AppWindow.Id, DisplayAreaFallback.Primary);
        if (displayArea != null)
        {
            int width = 360;
            int height = 500;
            int x = displayArea.WorkArea.X + displayArea.WorkArea.Width - width - 24;
            int y = displayArea.WorkArea.Y + displayArea.WorkArea.Height - height - 24;
            AppWindow.MoveAndResize(new RectInt32(x, y, width, height));
        }
    }

    private void OpenDashboard()
    {
        if (App.MainWindowInstance != null)
        {
            App.MainWindowInstance.Activate();
        }
    }
}

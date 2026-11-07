using System;
using Microsoft.UI.Xaml;
using Nexora.Desktop.ViewModels;
using Windows.Graphics;

namespace Nexora.Desktop;

public sealed partial class MainWindow : Window
{
    public MainViewModel ViewModel { get; }

    public MainWindow(MainViewModel viewModel)
    {
        ViewModel = viewModel ?? throw new ArgumentNullException(nameof(viewModel));
        this.InitializeComponent();

        if (Content is FrameworkElement root)
        {
            root.DataContext = ViewModel;
        }

        Title = "NEXORA Desktop Control Plane";
        AppWindow.Resize(new SizeInt32(1150, 780));
    }
}

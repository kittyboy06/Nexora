using System;
using Microsoft.UI;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Data;
using Microsoft.UI.Xaml.Media;
using Nexora.Desktop.Models;

namespace Nexora.Desktop.Converters;

public class BoolToVisibilityConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is bool b)
        {
            return b ? Visibility.Visible : Visibility.Collapsed;
        }
        return Visibility.Collapsed;
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        return value is Visibility v && v == Visibility.Visible;
    }
}

public class InverseBoolToVisibilityConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is bool b)
        {
            return b ? Visibility.Collapsed : Visibility.Visible;
        }
        return Visibility.Visible;
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        return value is Visibility v && v != Visibility.Visible;
    }
}

public class NullToVisibilityConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        return value != null ? Visibility.Visible : Visibility.Collapsed;
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}

public class StatusToBrushConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is bool b)
        {
            return b
                ? new SolidColorBrush(Windows.UI.Color.FromArgb(255, 46, 160, 67))      // Green
                : new SolidColorBrush(Windows.UI.Color.FromArgb(255, 209, 36, 47));     // Red
        }

        var statusStr = value?.ToString()?.ToUpperInvariant() ?? "";

        return statusStr switch
        {
            "COMPLETED" => new SolidColorBrush(Windows.UI.Color.FromArgb(255, 46, 160, 67)),      // Green
            "EXECUTING" or "RUNNING" => new SolidColorBrush(Windows.UI.Color.FromArgb(255, 0, 120, 212)), // Accent Blue
            "PLANNING" or "ROUTING" => new SolidColorBrush(Windows.UI.Color.FromArgb(255, 138, 99, 210)), // Purple
            "WAITING_APPROVAL" => new SolidColorBrush(Windows.UI.Color.FromArgb(255, 230, 140, 20)),     // Amber/Orange
            "FAILED" => new SolidColorBrush(Windows.UI.Color.FromArgb(255, 209, 36, 47)),          // Red
            "CANCELLED" => new SolidColorBrush(Windows.UI.Color.FromArgb(255, 120, 120, 120)),     // Slate Gray
            _ => new SolidColorBrush(Windows.UI.Color.FromArgb(255, 90, 90, 90)),
        };
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}

public class StatusToGlyphConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is bool b)
        {
            return b ? "\uE73E" : "\uE711";
        }

        var statusStr = value?.ToString()?.ToUpperInvariant() ?? "";

        return statusStr switch
        {
            "COMPLETED" => "\uE73E",       // Checkmark
            "EXECUTING" or "RUNNING" => "\uE768", // Play / Sync
            "PLANNING" or "ROUTING" => "\uE945",  // Brain / Gear
            "WAITING_APPROVAL" => "\uE7BA",      // Warning / Shield
            "FAILED" => "\uE711",                // Error X
            "CANCELLED" => "\uE71A",             // Blocked / Cancel
            _ => "\uE823",                       // Clock / Pending
        };
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}

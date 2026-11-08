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
    private static SolidColorBrush GetBrush(string resourceKey, Windows.UI.Color fallback)
    {
        try
        {
            if (Application.Current?.Resources != null)
            {
                if (Application.Current.Resources.TryGetValue(resourceKey, out var res) && res is SolidColorBrush brush)
                {
                    return brush;
                }
            }
        }
        catch
        {
            // Fallback for non-UI or test runner environments
        }
        return new SolidColorBrush(fallback);
    }

    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is bool b)
        {
            return b
                ? GetBrush("StatusSuccessBrush", Windows.UI.Color.FromArgb(255, 126, 186, 138))      // Warm Success Green
                : GetBrush("StatusDangerBrush", Windows.UI.Color.FromArgb(255, 240, 137, 127));     // Warm Danger Red
        }

        var statusStr = value?.ToString()?.ToUpperInvariant() ?? "";

        return statusStr switch
        {
            "COMPLETED" or "HEALTHY" => GetBrush("StatusSuccessBrush", Windows.UI.Color.FromArgb(255, 126, 186, 138)),
            "EXECUTING" or "RUNNING" or "PLANNING" or "ROUTING" => GetBrush("AccentCopperBrush", Windows.UI.Color.FromArgb(255, 201, 144, 93)), // Warm Copper
            "WAITING_APPROVAL" => GetBrush("StatusWarningBrush", Windows.UI.Color.FromArgb(255, 228, 180, 95)),     // Warm Warning Amber
            "BLOCKED" => GetBrush("StatusDangerBrush", Windows.UI.Color.FromArgb(255, 240, 137, 127)),
            "FAILED" or "ERROR" => GetBrush("StatusDangerBrush", Windows.UI.Color.FromArgb(255, 240, 137, 127)),
            "CANCELLED" => GetBrush("TextDisabledBrush", Windows.UI.Color.FromArgb(255, 141, 124, 109)),     // Clay Muted
            _ => GetBrush("TextSecondaryBrush", Windows.UI.Color.FromArgb(255, 200, 184, 165)),
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
            "COMPLETED" or "HEALTHY" => "\uE73E",       // Checkmark
            "EXECUTING" or "RUNNING" => "\uE768",      // Play / Sync
            "PLANNING" or "ROUTING" => "\uE945",       // Brain / Gear
            "WAITING_APPROVAL" => "\uE7BA",           // Warning / Shield
            "BLOCKED" => "\uE71A",                    // Blocked Circle
            "FAILED" or "ERROR" => "\uE711",           // Error X
            "CANCELLED" => "\uE71A",                  // Blocked / Cancel
            _ => "\uE823",                            // Clock / Pending
        };
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}

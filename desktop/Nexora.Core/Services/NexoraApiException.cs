using System;
using Nexora.Desktop.Models;

namespace Nexora.Desktop.Services;

public class NexoraApiException : Exception
{
    public string Code { get; }
    public int StatusCode { get; }
    public object? Details { get; }

    public NexoraApiException(string message, string code = "INTERNAL_ERROR", int statusCode = 500, object? details = null)
        : base(message)
    {
        Code = code;
        StatusCode = statusCode;
        Details = details;
    }

    public static NexoraApiException FromErrorResponse(ErrorResponse errorResponse, int statusCode)
    {
        var err = errorResponse.Error;
        var msg = err?.Message ?? $"HTTP error {statusCode}";
        if (err?.Details != null)
        {
            var detailsStr = err.Details.ToString();
            if (!string.IsNullOrWhiteSpace(detailsStr) && detailsStr != "[]")
            {
                msg = $"{msg} ({detailsStr})";
            }
        }
        return new NexoraApiException(
            message: msg,
            code: err?.Code ?? "API_ERROR",
            statusCode: statusCode,
            details: err?.Details
        );
    }
}

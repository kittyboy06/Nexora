using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Nexora.Desktop.Models;

public class SearchResultDto
{
    [JsonPropertyName("title")]
    public string Title { get; set; } = string.Empty;

    [JsonPropertyName("url")]
    public string Url { get; set; } = string.Empty;

    [JsonPropertyName("snippet")]
    public string Snippet { get; set; } = string.Empty;

    [JsonPropertyName("rank")]
    public int Rank { get; set; } = 1;
}

public class CitationItemDto
{
    [JsonPropertyName("quote")]
    public string Quote { get; set; } = string.Empty;

    [JsonPropertyName("source_url")]
    public string SourceUrl { get; set; } = string.Empty;

    [JsonPropertyName("char_offset")]
    public int CharOffset { get; set; }
}

public class FetchResultDto
{
    [JsonPropertyName("url")]
    public string Url { get; set; } = string.Empty;

    [JsonPropertyName("title")]
    public string Title { get; set; } = string.Empty;

    [JsonPropertyName("content")]
    public string Content { get; set; } = string.Empty;

    [JsonPropertyName("citations")]
    public List<CitationItemDto> Citations { get; set; } = new();

    [JsonPropertyName("content_hash")]
    public string ContentHash { get; set; } = string.Empty;

    [JsonPropertyName("http_status")]
    public int HttpStatus { get; set; } = 200;

    [JsonPropertyName("engine")]
    public string Engine { get; set; } = "http";

    [JsonPropertyName("screenshot_path")]
    public string? ScreenshotPath { get; set; }
}

public class ResearchEvidenceDto
{
    [JsonPropertyName("evidence_id")]
    public string EvidenceId { get; set; } = string.Empty;

    [JsonPropertyName("task_id")]
    public string TaskId { get; set; } = string.Empty;

    [JsonPropertyName("url")]
    public string Url { get; set; } = string.Empty;

    [JsonPropertyName("title")]
    public string Title { get; set; } = string.Empty;

    [JsonPropertyName("timestamp")]
    public string Timestamp { get; set; } = string.Empty;

    [JsonPropertyName("content_snippet")]
    public string ContentSnippet { get; set; } = string.Empty;

    [JsonPropertyName("content_hash")]
    public string ContentHash { get; set; } = string.Empty;

    [JsonPropertyName("citations")]
    public List<CitationItemDto> Citations { get; set; } = new();

    [JsonPropertyName("engine")]
    public string Engine { get; set; } = "http";

    [JsonPropertyName("screenshot_path")]
    public string? ScreenshotPath { get; set; }
}

public class QuarantineItemDto
{
    [JsonPropertyName("task_id")]
    public string TaskId { get; set; } = string.Empty;

    [JsonPropertyName("filename")]
    public string Filename { get; set; } = string.Empty;

    [JsonPropertyName("original_url")]
    public string OriginalUrl { get; set; } = string.Empty;

    [JsonPropertyName("file_size")]
    public long FileSize { get; set; }

    [JsonPropertyName("content_type")]
    public string ContentType { get; set; } = "application/octet-stream";

    [JsonPropertyName("sha256_hash")]
    public string Sha256Hash { get; set; } = string.Empty;

    [JsonPropertyName("quarantine_path")]
    public string QuarantinePath { get; set; } = string.Empty;

    [JsonPropertyName("downloaded_at")]
    public string DownloadedAt { get; set; } = string.Empty;
}

public class ResearchSearchRequestDto
{
    [JsonPropertyName("query")]
    public string Query { get; set; } = string.Empty;

    [JsonPropertyName("max_results")]
    public int MaxResults { get; set; } = 5;
}

public class ResearchFetchRequestDto
{
    [JsonPropertyName("url")]
    public string Url { get; set; } = string.Empty;

    [JsonPropertyName("render_js")]
    public bool RenderJs { get; set; }

    [JsonPropertyName("take_screenshot")]
    public bool TakeScreenshot { get; set; }
}

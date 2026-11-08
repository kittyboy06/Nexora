using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;

namespace Nexora.Desktop.ViewModels;

public partial class McpViewModel : ObservableObject
{
    private readonly INexoraApiClient _apiClient;

    [ObservableProperty]
    private bool _isLoading;

    [ObservableProperty]
    private string _statusMessage = string.Empty;

    [ObservableProperty]
    private McpServerRecordDto? _selectedServer;

    [ObservableProperty]
    private McpVaultItemSummaryDto? _selectedSecret;

    [ObservableProperty]
    private string _pingLatencyText = string.Empty;

    // Server creation form properties
    [ObservableProperty]
    private string _newServerId = string.Empty;

    [ObservableProperty]
    private string _newServerName = string.Empty;

    [ObservableProperty]
    private string _newServerDescription = string.Empty;

    [ObservableProperty]
    private string _newServerCommand = string.Empty;

    [ObservableProperty]
    private string _newServerArgs = string.Empty;

    [ObservableProperty]
    private string _newServerEnv = string.Empty;

    [ObservableProperty]
    private string _newServerWorkingDir = string.Empty;

    // Safe Onboarding Wizard (Phase 15)
    [ObservableProperty]
    private McpInspectionReportDto? _inspectionReport;

    [ObservableProperty]
    private McpTestConnectionResultDto? _testResult;

    [ObservableProperty]
    private bool _isOnboardInspecting;

    [ObservableProperty]
    private bool _isOnboardTesting;

    // Vault creation form properties
    [ObservableProperty]
    private string _newSecretKey = string.Empty;

    [ObservableProperty]
    private string _newSecretValue = string.Empty;

    [ObservableProperty]
    private string _newSecretDescription = string.Empty;

    public ObservableCollection<McpServerRecordDto> Servers { get; } = new();
    public ObservableCollection<McpToolDefinitionDto> AdvertisedTools { get; } = new();
    public ObservableCollection<McpVaultItemSummaryDto> VaultSecrets { get; } = new();

    public McpViewModel(INexoraApiClient apiClient)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));
    }

    [RelayCommand]
    public async Task LoadServersAsync()
    {
        IsLoading = true;
        StatusMessage = "Loading MCP servers...";
        try
        {
            var list = await _apiClient.ListMcpServersAsync();
            Servers.Clear();
            foreach (var s in list)
            {
                Servers.Add(s);
            }

            if (SelectedServer != null)
            {
                var refreshed = Servers.FirstOrDefault(s => s.Config.Id == SelectedServer.Config.Id);
                SelectServer(refreshed);
            }
            StatusMessage = $"Loaded {Servers.Count} MCP servers.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to load MCP servers: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task LoadVaultSecretsAsync()
    {
        IsLoading = true;
        StatusMessage = "Loading encrypted vault secrets...";
        try
        {
            var secrets = await _apiClient.ListMcpVaultSecretsAsync();
            VaultSecrets.Clear();
            foreach (var s in secrets)
            {
                VaultSecrets.Add(s);
            }
            StatusMessage = $"Loaded {VaultSecrets.Count} vault secrets.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to load vault secrets: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    public void SelectServer(McpServerRecordDto? server)
    {
        SelectedServer = server;
        AdvertisedTools.Clear();
        PingLatencyText = string.Empty;

        if (server != null)
        {
            foreach (var t in server.AdvertisedTools)
            {
                AdvertisedTools.Add(t);
            }
            if (server.PingLatencyMs.HasValue)
            {
                PingLatencyText = $"{server.PingLatencyMs.Value:F1} ms";
            }
        }
    }

    [RelayCommand]
    public async Task ApproveServerAsync(string? serverId)
    {
        var id = serverId ?? SelectedServer?.Config.Id;
        if (string.IsNullOrWhiteSpace(id)) return;

        IsLoading = true;
        StatusMessage = $"Approving server '{id}'...";
        try
        {
            var updated = await _apiClient.ApproveMcpServerAsync(id);
            UpdateServerInCollection(updated);
            StatusMessage = $"Server '{id}' approved by operator.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Approval failed: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task ConnectServerAsync(string? serverId)
    {
        var id = serverId ?? SelectedServer?.Config.Id;
        if (string.IsNullOrWhiteSpace(id)) return;

        IsLoading = true;
        StatusMessage = $"Connecting to server '{id}'...";
        try
        {
            var updated = await _apiClient.ConnectMcpServerAsync(id);
            UpdateServerInCollection(updated);
            StatusMessage = $"Connected to '{id}'. {updated.AdvertisedTools.Count} tools registered.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Connect failed: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task DisconnectServerAsync(string? serverId)
    {
        var id = serverId ?? SelectedServer?.Config.Id;
        if (string.IsNullOrWhiteSpace(id)) return;

        IsLoading = true;
        StatusMessage = $"Disconnecting server '{id}'...";
        try
        {
            var updated = await _apiClient.DisconnectMcpServerAsync(id);
            UpdateServerInCollection(updated);
            StatusMessage = $"Disconnected server '{id}'.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Disconnect failed: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task PingServerAsync(string? serverId)
    {
        var id = serverId ?? SelectedServer?.Config.Id;
        if (string.IsNullOrWhiteSpace(id)) return;

        IsLoading = true;
        StatusMessage = $"Pinging server '{id}'...";
        try
        {
            var resp = await _apiClient.PingMcpServerAsync(id);
            PingLatencyText = $"{resp.LatencyMs:F1} ms";
            StatusMessage = $"Ping reply from '{id}' in {resp.LatencyMs:F1} ms.";
        }
        catch (Exception ex)
        {
            PingLatencyText = "Error";
            StatusMessage = $"Ping failed: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task DeleteServerAsync(string? serverId)
    {
        var id = serverId ?? SelectedServer?.Config.Id;
        if (string.IsNullOrWhiteSpace(id)) return;

        IsLoading = true;
        StatusMessage = $"Deleting server '{id}'...";
        try
        {
            var ok = await _apiClient.DeleteMcpServerAsync(id);
            if (ok)
            {
                var existing = Servers.FirstOrDefault(s => s.Config.Id == id);
                if (existing != null)
                {
                    Servers.Remove(existing);
                }
                if (SelectedServer?.Config.Id == id)
                {
                    SelectServer(null);
                }
                StatusMessage = $"Deleted server '{id}'.";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Delete failed: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    private McpServerCreateRequestDto BuildCreateRequest()
    {
        var args = string.IsNullOrWhiteSpace(NewServerArgs)
            ? new List<string>()
            : NewServerArgs.Split(' ', StringSplitOptions.RemoveEmptyEntries).ToList();

        var env = new Dictionary<string, string>();
        if (!string.IsNullOrWhiteSpace(NewServerEnv))
        {
            var lines = NewServerEnv.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
            foreach (var line in lines)
            {
                var idx = line.IndexOf('=');
                if (idx > 0)
                {
                    var k = line.Substring(0, idx).Trim();
                    var v = line.Substring(idx + 1).Trim();
                    env[k] = v;
                }
            }
        }

        return new McpServerCreateRequestDto
        {
            Id = NewServerId.Trim().ToLowerInvariant(),
            Name = string.IsNullOrWhiteSpace(NewServerName) ? NewServerId.Trim() : NewServerName.Trim(),
            Description = NewServerDescription.Trim(),
            Command = NewServerCommand.Trim(),
            Args = args,
            Env = env,
            WorkingDir = string.IsNullOrWhiteSpace(NewServerWorkingDir) ? null : NewServerWorkingDir.Trim(),
        };
    }

    [RelayCommand]
    public async Task InspectNewServerAsync()
    {
        if (string.IsNullOrWhiteSpace(NewServerCommand))
        {
            StatusMessage = "Please specify an executable command to inspect.";
            return;
        }

        IsOnboardInspecting = true;
        StatusMessage = "Inspecting manifest for security risks...";
        try
        {
            var req = BuildCreateRequest();
            InspectionReport = await _apiClient.InspectMcpManifestAsync(req);
            StatusMessage = InspectionReport.IsValid
                ? $"Manifest inspected safely. Fingerprint: {InspectionReport.Fingerprint[..8]}... (Risk: {InspectionReport.RiskLevel})"
                : $"Security warnings detected ({InspectionReport.Warnings.Count}). Review required.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Inspection error: {ex.Message}";
        }
        finally
        {
            IsOnboardInspecting = false;
        }
    }

    [RelayCommand]
    public async Task TestNewServerConnectionAsync()
    {
        if (string.IsNullOrWhiteSpace(NewServerCommand))
        {
            StatusMessage = "Please specify an executable command to test.";
            return;
        }

        IsOnboardTesting = true;
        StatusMessage = "Performing safe non-executing handshake probe...";
        try
        {
            var req = BuildCreateRequest();
            TestResult = await _apiClient.TestMcpConnectionAsync(req);
            StatusMessage = TestResult.Success
                ? $"Probe succeeded ({TestResult.LatencyMs}ms). Discovered {TestResult.DiscoveredToolsCount} tools. Process terminated."
                : $"Connection probe failed: {TestResult.ErrorMessage}";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Probe failed: {ex.Message}";
        }
        finally
        {
            IsOnboardTesting = false;
        }
    }

    [RelayCommand]
    public async Task ApproveAndRegisterAsync()
    {
        if (string.IsNullOrWhiteSpace(NewServerId) || string.IsNullOrWhiteSpace(NewServerCommand))
        {
            StatusMessage = "Server ID and Command are required.";
            return;
        }

        try
        {
            StatusMessage = "Registering MCP server...";
            var req = BuildCreateRequest();
            var registered = await _apiClient.RegisterMcpServerAsync(req);

            StatusMessage = "Binding cryptographic approval fingerprint...";
            var approved = await _apiClient.ApproveMcpManifestAsync(new McpOnboardApproveRequestDto
            {
                ServerId = registered.Config.Id,
                Fingerprint = registered.Fingerprint,
                Operator = "operator"
            });

            ClearNewServerForm();
            await LoadServersAsync();
            StatusMessage = $"Server '{approved.Config.Name}' registered & approved with fingerprint {approved.Fingerprint[..8]}...";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Registration failed: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task RegisterServerAsync()
    {
        if (string.IsNullOrWhiteSpace(NewServerId) || string.IsNullOrWhiteSpace(NewServerCommand))
        {
            StatusMessage = "Server ID and Command are required.";
            return;
        }

        IsLoading = true;
        StatusMessage = $"Registering server '{NewServerId}'...";
        try
        {
            var req = BuildCreateRequest();
            var created = await _apiClient.RegisterMcpServerAsync(req);
            Servers.Add(created);
            SelectServer(created);

            ClearNewServerForm();
            StatusMessage = $"Registered server '{created.Config.Id}' (requires operator approval).";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Registration error: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    private void ClearNewServerForm()
    {
        NewServerId = string.Empty;
        NewServerName = string.Empty;
        NewServerDescription = string.Empty;
        NewServerCommand = string.Empty;
        NewServerArgs = string.Empty;
        NewServerEnv = string.Empty;
        NewServerWorkingDir = string.Empty;
        InspectionReport = null;
        TestResult = null;
    }

    [RelayCommand]
    public async Task SaveSecretAsync()
    {
        if (string.IsNullOrWhiteSpace(NewSecretKey) || string.IsNullOrWhiteSpace(NewSecretValue))
        {
            StatusMessage = "Secret Key and Value are required.";
            return;
        }

        IsLoading = true;
        StatusMessage = $"Encrypting and saving secret '{NewSecretKey}'...";
        try
        {
            var req = new McpVaultWriteRequestDto
            {
                Key = NewSecretKey.Trim(),
                SecretValue = NewSecretValue,
                Description = NewSecretDescription.Trim(),
            };

            var summary = await _apiClient.WriteMcpVaultSecretAsync(req);

            var existing = VaultSecrets.FirstOrDefault(v => v.Key == summary.Key);
            if (existing != null)
            {
                var index = VaultSecrets.IndexOf(existing);
                VaultSecrets[index] = summary;
            }
            else
            {
                VaultSecrets.Add(summary);
            }

            NewSecretKey = string.Empty;
            NewSecretValue = string.Empty;
            NewSecretDescription = string.Empty;

            StatusMessage = $"Secret '{summary.Key}' encrypted and saved in local vault.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to save secret: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task DeleteSecretAsync(string? key)
    {
        var k = key ?? SelectedSecret?.Key;
        if (string.IsNullOrWhiteSpace(k)) return;

        IsLoading = true;
        StatusMessage = $"Deleting vault secret '{k}'...";
        try
        {
            var ok = await _apiClient.DeleteMcpVaultSecretAsync(k);
            if (ok)
            {
                var existing = VaultSecrets.FirstOrDefault(v => v.Key == k);
                if (existing != null)
                {
                    VaultSecrets.Remove(existing);
                }
                if (SelectedSecret?.Key == k)
                {
                    SelectedSecret = null;
                }
                StatusMessage = $"Deleted vault secret '{k}'.";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to delete secret: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    private void UpdateServerInCollection(McpServerRecordDto record)
    {
        var existing = Servers.FirstOrDefault(s => s.Config.Id == record.Config.Id);
        if (existing != null)
        {
            var idx = Servers.IndexOf(existing);
            Servers[idx] = record;
        }
        else
        {
            Servers.Add(record);
        }

        if (SelectedServer?.Config.Id == record.Config.Id)
        {
            SelectServer(record);
        }
    }
}

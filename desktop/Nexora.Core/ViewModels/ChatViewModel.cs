using System;
using System.Collections.ObjectModel;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;

namespace Nexora.Desktop.ViewModels;

public partial class ChatViewModel : ObservableObject
{
    private readonly INexoraApiClient _apiClient;

    public ObservableCollection<Conversation> Conversations { get; } = new();
    public ObservableCollection<ConversationMessage> Messages { get; } = new();
    public ObservableCollection<ConversationWorkItem> WorkItems { get; } = new();

    [ObservableProperty]
    private Conversation? _currentConversation;

    [ObservableProperty]
    private string _composerText = string.Empty;

    [ObservableProperty]
    private ChatMode _selectedMode = ChatMode.Auto;

    public string SelectedModeTag
    {
        get => SelectedMode switch
        {
            ChatMode.AnswerOnly => "answer_only",
            ChatMode.Task => "task",
            ChatMode.Research => "research",
            ChatMode.DesktopVision => "desktop_vision",
            ChatMode.Schedule => "schedule",
            _ => "auto"
        };
        set
        {
            SelectedMode = value switch
            {
                "answer_only" => ChatMode.AnswerOnly,
                "task" => ChatMode.Task,
                "research" => ChatMode.Research,
                "desktop_vision" => ChatMode.DesktopVision,
                "schedule" => ChatMode.Schedule,
                _ => ChatMode.Auto
            };
            OnPropertyChanged();
            OnPropertyChanged(nameof(SelectedMode));
        }
    }

    [ObservableProperty]
    private string _selectedModelOverride = string.Empty;

    [ObservableProperty]
    private bool _isSending;

    [ObservableProperty]
    private string? _errorMessage;

    public event Action<ConversationWorkItem>? WorkItemNavigationRequested;

    public ChatViewModel(INexoraApiClient apiClient)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));
    }

    [RelayCommand]
    public async Task LoadConversationsAsync()
    {
        try
        {
            var list = await _apiClient.ListConversationsAsync();
            Conversations.Clear();
            foreach (var conv in list)
            {
                Conversations.Add(conv);
            }

            if (CurrentConversation == null && Conversations.Count > 0)
            {
                await SelectConversationAsync(Conversations[0]);
            }
            else if (Conversations.Count == 0)
            {
                await NewConversationAsync();
            }
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Failed loading conversations: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task SelectConversationAsync(Conversation? conversation)
    {
        if (conversation == null) return;
        try
        {
            var full = await _apiClient.GetConversationAsync(conversation.ConversationId);
            CurrentConversation = full;
            Messages.Clear();
            foreach (var m in full.Messages)
            {
                Messages.Add(m);
            }
            WorkItems.Clear();
            foreach (var w in full.WorkItems)
            {
                WorkItems.Add(w);
            }
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Failed loading transcript: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task NewConversationAsync()
    {
        try
        {
            var newConv = await _apiClient.CreateConversationAsync();
            Conversations.Insert(0, newConv);
            CurrentConversation = newConv;
            Messages.Clear();
            WorkItems.Clear();
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Failed creating conversation: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task DeleteConversationAsync(Conversation? conversation)
    {
        if (conversation == null) return;
        try
        {
            await _apiClient.DeleteConversationAsync(conversation.ConversationId);
            Conversations.Remove(conversation);
            if (CurrentConversation?.ConversationId == conversation.ConversationId)
            {
                if (Conversations.Count > 0)
                {
                    await SelectConversationAsync(Conversations[0]);
                }
                else
                {
                    await NewConversationAsync();
                }
            }
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Failed deleting conversation: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task SendMessageAsync()
    {
        if (string.IsNullOrWhiteSpace(ComposerText) || IsSending)
        {
            return;
        }

        if (CurrentConversation == null)
        {
            await NewConversationAsync();
        }

        if (CurrentConversation == null) return;

        var text = ComposerText.Trim();
        ComposerText = string.Empty;
        IsSending = true;
        ErrorMessage = null;

        // Optimistically add user turn
        var userTurn = new ConversationMessage(
            MessageId: $"temp_{Guid.NewGuid():N}",
            ConversationId: CurrentConversation.ConversationId,
            Role: "user",
            Content: text,
            Mode: SelectedMode,
            Model: string.IsNullOrWhiteSpace(SelectedModelOverride) ? null : SelectedModelOverride,
            Routing: null,
            WorkItemIds: new(),
            CreatedAt: DateTimeOffset.UtcNow
        );
        Messages.Add(userTurn);

        try
        {
            var overrideModel = string.IsNullOrWhiteSpace(SelectedModelOverride) ? null : SelectedModelOverride;
            var response = await _apiClient.SendChatMessageAsync(
                CurrentConversation.ConversationId,
                text,
                SelectedMode,
                overrideModel
            );

            Messages.Add(response.Message);
            if (response.WorkItem != null)
            {
                WorkItems.Add(response.WorkItem);
            }
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Chat response failed: {ex.Message}";
        }
        finally
        {
            IsSending = false;
        }
    }

    [RelayCommand]
    public void NavigateToWorkItem(ConversationWorkItem? item)
    {
        if (item != null)
        {
            WorkItemNavigationRequested?.Invoke(item);
        }
    }
}

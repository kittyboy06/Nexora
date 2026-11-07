# Specification: Standalone Executable, Mock Data Purge & Dynamic Model Autonomy

**Document Version:** 1.0.0  
**Status:** Approved for Implementation  
**Target Architecture:** Windows 10/11 (x64)  
**Deliverables:** Single-file standalone executable (`Nexora.exe`), pure production tool registry, dynamic Ollama model auto-discovery.

---

## 1. Executive Summary

This specification defines the architectural transformation of NEXORA from a multi-process developer environment into a **true single-file standalone distribution (`Nexora.exe`)**. It eliminates all historical mock tools and simulated fallbacks from the production codebase, decouples the platform from any hardcoded LLM model tags (`qwen3.5:9b`), and implements dynamic active model discovery against local Ollama installations.

When completed, an operator will simply double-click `Nexora.exe` on any Windows 10/11 machine. The single executable will launch the native WinUI 3 desktop client, silently supervise the frozen backend engine via Windows Job Objects, and auto-detect whatever models the operator has installed in local Ollama (Llama, Mistral, Qwen, Phi, DeepSeek, etc.).

---

## 2. Architectural Pillars & Core Changes

### 2.1. Pillar 1: Production Mock Data & Simulated Adapter Purge

#### 2.1.1. Eliminate Mock Tools from Runtime Registries
* Remove `register_mock_tools(tool_registry)` from:
  - `backend/app/main.py`
  - `backend/app/api/dependencies.py`
* Relocate `backend/app/tools/mock_tools/` to `backend/tests/fixtures/mock_tools/`. Production runtime will only register real tools:
  - **Filesystem Tools** (`file_create`, `file_read`, `file_edit`, `file_delete`, `file_list`, `file_search`, `file_rename`, `file_copy`, `file_move`)
  - **Terminal Tools** (`terminal_execute`, `terminal_run_script`)
  - **Windows Tools** (`app_launch`, `app_list`, `app_find`)
  - **Research Tools** (`web_search`, `web_fetch`, `web_extract_citations`, `web_download_quarantine`)
  - **Memory Tools** (`memory_search`, `memory_store`, `memory_retrieve`, `memory_revoke`)
  - **Desktop Vision Tools** (`desktop_bind_window`, `desktop_inspect_tree`, `desktop_click_element`, `desktop_type_text`)
  - **Dynamic MCP Tools** (registered on-demand via MCP stdio servers)
* Update test suites that explicitly test mock tool behaviors (`test_executor.py`, `test_tools.py`, etc.) to import from `backend.tests.fixtures.mock_tools`.

#### 2.1.2. Real Win32 GDI Bitmap Capture in Production
* In `backend/app/desktop/win32_adapter.py`:
  - Implement genuine GDI bitmap extraction using `GetDIBits` and Pillow:
    ```python
    # Allocate BITMAPINFO and extract pixels
    bmp_info = BITMAPINFO(...)
    self._gdi32.GetDIBits(mem_dc, bitmap, 0, height, buf, byref(bmp_info), DIB_RGB_COLORS)
    image = Image.frombuffer("RGBA", (width, height), buf, "raw", "BGRA", 0, 1)
    # Save to PNG in memory buffer
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format="PNG")
    return img_byte_arr.getvalue(), width, height
    ```
  - Completely eliminate all imports of `DUMMY_PNG_BYTES` from `win32_adapter.py`.
* Relocate `backend/app/desktop/mock_adapter.py` to `backend/tests/fixtures/desktop_mock_adapter.py`.

---

### 2.2. Pillar 2: Complete Model Independence & Auto-Discovery

#### 2.2.1. Zero Hardcoded Models in Core Configuration
* In `backend/app/core/config.py`:
  - `OLLAMA_MODEL: str = ""` (defaults to empty string).
  - `MODEL_ROUTER_MODEL: str = ""`.
* In `backend/app/cli/doctor.py`:
  - Remove hardcoded recommendation `Run 'ollama pull qwen2.5:7b'`.
  - Replace with dynamic recommendation: `Run 'ollama pull <model_name>' (e.g. llama3.1, mistral, qwen2.5)`.

#### 2.2.2. Dynamic Active Model Resolution in `OllamaService`
* Implement `resolve_active_model()` in `backend/app/services/ollama_service.py`:
  1. Calls `/api/tags` to get currently installed models from local Ollama.
  2. If `settings.OLLAMA_MODEL` is configured and matches an installed model, use it.
  3. If not set or not installed, automatically select the first installed model from Ollama.
  4. If no models are installed, raise `ModelNotFoundException("No models installed in local Ollama. Please run 'ollama pull <model>'.")`.
* Cache the resolved active model in-memory with a `set_active_model(model_name: str)` method.
* Expose API endpoint:
  - `POST /api/ollama/active-model` with body `{"model": "..."}` to allow switching models dynamically from the WinUI 3 desktop client.

#### 2.2.3. Model-Agnostic Profiles (`data/model_profiles.json`)
* In `data/model_profiles.json`, update all 5 specialist profiles:
  - Change `"model": "qwen3.5:9b"` to `"model": "auto"`.
* In `backend/app/services/model_registry.py`:
  - When a profile's `model` is `"auto"` or empty, resolve it dynamically to the current active model from `OllamaService`.
  - Specialist profiles describe capabilities and system prompts independently of the underlying model weights.

---

### 2.3. Pillar 3: Single Standalone Executable Packaging (`Nexora.exe`)

#### 2.3.1. Embedded Frozen Server Architecture
```
┌────────────────────────────────────────────────────────────────────────┐
│ Nexora.exe (Single Standalone Executable)                              │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ WinUI 3 Desktop Frontend (.NET 8 PublishSingleFile, x64)         │  │
│  │                                                                  │  │
│  │  Embedded Assembly Resource:                                     │  │
│  │    Nexora.Desktop.Resources.nexora-server.exe                   │  │
│  │    (Frozen Python 3.14+ FastAPI Engine via PyInstaller)         │  │
│  └─────────────────────────────────┬────────────────────────────────┘  │
│                                    │ Extracts to LocalAppData on boot  │
│                                    ▼                                   │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Hidden Background Process: %LOCALAPPDATA%\Nexora\bin\server.exe   │  │
│  │ Bound to Windows Job Object: KILL_ON_JOB_CLOSE (0 zombie tasks) │  │
│  │ Binds exclusively to Loopback: 127.0.0.1:8000                    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

#### 2.3.2. Lifecycle Supervisor with Job Object Containment
* In `desktop/Nexora.Core/Services/BackendSupervisor.cs`:
  - On application startup:
    1. Probe `http://127.0.0.1:8000/api/health`.
    2. If not running, extract embedded `nexora-server.exe` to `%LOCALAPPDATA%\Nexora\bin\nexora-server.exe`.
    3. Create a Win32 Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
    4. Launch `nexora-server.exe` hidden (`CreateNoWindow = true`, `UseShellExecute = false`).
    5. Assign child process to the Job Object.
    6. Poll `/api/health` until ready (up to 15s).
  - On application exit:
    - Calling `Dispose()` or window close triggers process kill; Job Object guarantees immediate teardown even if UI is force-killed via Task Manager.

#### 2.3.3. Build & Packaging Automation
* Create `scripts/package-standalone.ps1`:
  1. Freeze backend:
     ```powershell
     python -m PyInstaller --noconfirm --clean --onefile --name nexora-server `
         --paths "$ProjectRoot" `
         --collect-submodules backend `
         --distpath "$ProjectRoot\desktop\Nexora.Desktop\Resources" `
         "$ProjectRoot\backend\server_entrypoint.py"
     ```
  2. Embed in `.csproj`:
     ```xml
     <ItemGroup>
       <EmbeddedResource Include="Resources\nexora-server.exe" />
     </ItemGroup>
     ```
  3. Publish single-file desktop client:
     ```powershell
     dotnet publish desktop/Nexora.Desktop/Nexora.Desktop.csproj `
         -c Release -r win-x64 -p:Platform=x64 `
         -p:PublishSingleFile=true `
         -p:SelfContained=true `
         -p:IncludeNativeLibrariesForSelfExtract=true `
         -o "$ProjectRoot\dist\standalone"
     ```
  4. Output: `dist\standalone\Nexora.exe`.

---

## 3. Verification Criteria
1. **Mock Data Zero-Presence Gate:** Zero references to `mock_tools` in `backend/app/`. All production tool registries contain only genuine tools.
2. **Dynamic Model Discovery Gate:** Successfully starts and plans with any arbitrary model tag installed in local Ollama without editing code or config.
3. **Single Executable Gate:** `dist\standalone\Nexora.exe` is a single standalone file. Running it launches the full WinUI 3 dashboard, automatically spins up the backend on port 8000, connects, and cleanly tears down on exit.
4. **Hermetic Regression Gate:** All 328 backend unit tests and 49 desktop unit tests pass with zero regressions.

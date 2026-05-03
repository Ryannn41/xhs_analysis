const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const BACKEND_HOST = process.env.BACKEND_HOST || "127.0.0.1";
const BACKEND_PORT = Number(process.env.BACKEND_PORT || "8000");
const HEALTH_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}/health`;

let backendProcess = null;
let backendStartError = null;
let backendReady = false;
let backendOutput = "";
let mainWindow = null;

function waitForBackend(timeoutMs = 45000) {
  const startedAt = Date.now();

  return new Promise((resolve, reject) => {
    function check() {
      const request = http.get(HEALTH_URL, (response) => {
        response.resume();
        if (response.statusCode && response.statusCode >= 200 && response.statusCode < 300) {
          backendReady = true;
          resolve();
          return;
        }
        retry();
      });

      request.on("error", retry);
      request.setTimeout(2000, () => {
        request.destroy();
        retry();
      });
    }

    function retry() {
      if (backendStartError) {
        reject(backendStartError);
        return;
      }
      if (Date.now() - startedAt > timeoutMs) {
        reject(new Error(`后端启动超时：${HEALTH_URL}`));
        return;
      }
      setTimeout(check, 500);
    }

    check();
  });
}

function getBackendCommand() {
  if (app.isPackaged) {
    return {
      command: path.join(process.resourcesPath, "backend", "backend.exe"),
      args: [],
      cwd: process.resourcesPath,
    };
  }

  const python = process.env.PYTHON || "python";
  return {
    command: python,
    args: [
      "-m",
      "uvicorn",
      "backend.app:app",
      "--host",
      BACKEND_HOST,
      "--port",
      String(BACKEND_PORT),
    ],
    cwd: path.join(__dirname, ".."),
  };
}

function startBackend() {
  if (backendProcess) {
    return;
  }
  backendStartError = null;
  backendReady = false;
  backendOutput = "";

  const backend = getBackendCommand();
  const userDataDir = app.getPath("userData");
  const env = {
    ...process.env,
    BACKEND_HOST,
    BACKEND_PORT: String(BACKEND_PORT),
    BROWSER_HEADLESS: process.env.BROWSER_HEADLESS || "false",
    XHS_DESKTOP_MODE: "true",
    XHS_USER_DATA_DIR: userDataDir,
    FRONTEND_ORIGINS: "http://localhost:5173,http://127.0.0.1:5173,null",
  };

  if (app.isPackaged) {
    env.PLAYWRIGHT_BROWSERS_PATH = path.join(process.resourcesPath, "ms-playwright");
  }

  backendProcess = spawn(backend.command, backend.args, {
    cwd: backend.cwd,
    env,
    stdio: app.isPackaged ? ["ignore", "pipe", "pipe"] : "inherit",
    windowsHide: true,
  });

  if (app.isPackaged) {
    const appendOutput = (chunk) => {
      backendOutput = `${backendOutput}${chunk.toString()}`.slice(-4000);
    };
    backendProcess.stdout?.on("data", appendOutput);
    backendProcess.stderr?.on("data", appendOutput);
  }

  backendProcess.on("exit", (code, signal) => {
    if (!backendReady) {
      const detail = backendOutput.trim();
      backendStartError = new Error(
        `后端进程已退出（code=${code ?? "null"}, signal=${signal ?? "null"}）${detail ? `\n${detail}` : ""}`,
      );
    }
    backendProcess = null;
  });
  backendProcess.on("error", (error) => {
    backendStartError = error;
    backendProcess = null;
  });
}

function stopBackend() {
  if (!backendProcess) {
    return;
  }

  const child = backendProcess;
  backendProcess = null;
  child.kill();
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 900,
    minWidth: 1024,
    minHeight: 720,
    title: "小红书账号分析",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (app.isPackaged) {
    mainWindow.loadFile(path.join(__dirname, "..", "frontend", "dist", "index.html"));
  } else {
    mainWindow.loadURL(process.env.ELECTRON_START_URL || "http://127.0.0.1:5173");
  }

  if (!app.isPackaged && process.env.ELECTRON_OPEN_DEVTOOLS === "true") {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

async function boot() {
  try {
    startBackend();
    await waitForBackend();
    createWindow();
  } catch (error) {
    dialog.showErrorBox(
      "启动失败",
      error instanceof Error ? error.message : "本地后端启动失败，请重新打开应用。",
    );
    app.quit();
  }
}

app.whenReady().then(boot);

app.on("before-quit", stopBackend);

app.on("window-all-closed", () => {
  app.quit();
});

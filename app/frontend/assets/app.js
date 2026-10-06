/* ============================================================
   Clip_ S
   Frontend application controller
   ============================================================ */

"use strict";


/* ============================================================
   DOM ELEMENTS
   ============================================================ */

const fileInput = document.getElementById("fileInput");
const uploadCard = document.getElementById("uploadCard");
const projectCard = document.getElementById("projectCard");

const filenameEl = document.getElementById("filename");
const jobStatus = document.getElementById("jobStatus");

const progressBar = document.getElementById("progressBar");
const progressText = document.getElementById("progressText");
const jobMessage = document.getElementById("jobMessage");

const metadataSection = document.getElementById("metadataSection");
const metadataGrid = document.getElementById("metadataGrid");

const clipPrompt = document.getElementById("clipPrompt");
const analyzeButton = document.getElementById("analyzeButton");

const candidateSection = document.getElementById("candidateSection");
const candidateGrid = document.getElementById("candidateGrid");

const outputSection = document.getElementById("outputSection");
const outputGrid = document.getElementById("outputGrid");

const errorBox = document.getElementById("errorBox");

const newProjectButton =
  document.getElementById("newProjectButton");

const serverStatus =
  document.getElementById("serverStatus");

const toast =
  document.getElementById("toast");


/* ============================================================
   APPLICATION STATE
   ============================================================ */

const state = {
  currentJobId: null,
  currentFile: null,
  currentJob: null,
  pollingTimer: null,
  pollInProgress: false,
  analysisRequested: false,
};


/* ============================================================
   INITIALIZATION
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
  initializeNavigation();
  initializeUpload();
  initializeDragAndDrop();
  initializeSuggestions();
  initializeProjectControls();
  initializeAnalysis();

  checkServer();

  window.setInterval(checkServer, 30000);
});


/* ============================================================
   NAVIGATION
   ============================================================ */

function initializeNavigation() {
  const navigationButtons =
    document.querySelectorAll("[data-section]");

  navigationButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const section =
        button.dataset.section;

      if (!section) {
        return;
      }

      switchSection(section);
    });
  });
}


function switchSection(sectionName) {
  const sections =
    document.querySelectorAll(".page-section");

  const navLinks =
    document.querySelectorAll(".nav-link");

  sections.forEach((section) => {
    section.classList.remove("active-section");
  });

  navLinks.forEach((link) => {
    link.classList.remove("active");
  });

  const targetSection =
    document.getElementById(
      `section-${sectionName}`
    );

  if (targetSection) {
    targetSection.classList.add("active-section");
  }

  const matchingNav =
    document.querySelector(
      `.nav-link[data-section="${CSS.escape(sectionName)}"]`
    );

  if (matchingNav) {
    matchingNav.classList.add("active");
  }

  window.scrollTo({
    top: 0,
    behavior: "smooth",
  });
}


/* ============================================================
   SERVER STATUS
   ============================================================ */

async function checkServer() {
  try {
    const response =
      await fetch("/health", {
        method: "GET",
        headers: {
          "Accept": "application/json",
        },
        cache: "no-store",
      });

    if (!response.ok) {
      throw new Error("Server unavailable");
    }

    const data =
      await response.json();

    if (data.success) {
      setServerStatus(
        "System online",
        "online"
      );
    } else {
      setServerStatus(
        "System unavailable",
        "offline"
      );
    }

  } catch (error) {
    setServerStatus(
      "Offline",
      "offline"
    );
  }
}


function setServerStatus(message, status) {
  if (!serverStatus) {
    return;
  }

  serverStatus.textContent =
    message;

  const dot =
    document.querySelector(".status-dot");

  if (!dot) {
    return;
  }

  dot.style.background =
    status === "online"
      ? "var(--success)"
      : "var(--danger)";

  dot.style.boxShadow =
    status === "online"
      ? "0 0 0 4px rgba(85,214,138,.08), 0 0 15px rgba(85,214,138,.35)"
      : "0 0 0 4px rgba(255,109,125,.08), 0 0 15px rgba(255,109,125,.30)";
}


/* ============================================================
   FILE UPLOAD
   ============================================================ */

function initializeUpload() {
  if (!fileInput) {
    return;
  }

  fileInput.addEventListener(
    "change",
    () => {
      const file =
        fileInput.files?.[0];

      if (file) {
        uploadVideo(file);
      }
    }
  );
}


function initializeDragAndDrop() {
  if (!uploadCard) {
    return;
  }

  const dragEvents = [
    "dragenter",
    "dragover",
  ];

  dragEvents.forEach((eventName) => {
    uploadCard.addEventListener(
      eventName,
      (event) => {
        event.preventDefault();
        event.stopPropagation();

        uploadCard.classList.add(
          "dragging"
        );
      }
    );
  });

  [
    "dragleave",
    "drop",
  ].forEach((eventName) => {
    uploadCard.addEventListener(
      eventName,
      (event) => {
        event.preventDefault();
        event.stopPropagation();

        uploadCard.classList.remove(
          "dragging"
        );
      }
    );
  });

  uploadCard.addEventListener(
    "drop",
    (event) => {
      const files =
        event.dataTransfer?.files;

      if (!files || !files.length) {
        return;
      }

      const file =
        files[0];

      uploadVideo(file);
    }
  );
}


/* ============================================================
   FILE VALIDATION
   ============================================================ */

function validateSelectedFile(file) {
  if (!file) {
    return {
      valid: false,
      message: "Please select a video.",
    };
  }

  if (!file.type.startsWith("video/")) {
    return {
      valid: false,
      message: "Please select a valid video file.",
    };
  }

  const allowedExtensions = [
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".m4v",
    ".avi",
  ];

  const filename =
    file.name.toLowerCase();

  const validExtension =
    allowedExtensions.some(
      (extension) =>
        filename.endsWith(extension)
    );

  if (!validExtension) {
    return {
      valid: false,
      message:
        "Unsupported video format. Use MP4, MOV, MKV, WEBM, M4V or AVI.",
    };
  }

  return {
    valid: true,
    message: "",
  };
}


/* ============================================================
   UPLOAD VIDEO
   ============================================================ */

async function uploadVideo(file) {
  const validation =
    validateSelectedFile(file);

  if (!validation.valid) {
    showError(
      validation.message
    );

    showToast(
      validation.message
    );

    return;
  }

  clearError();

  resetProcessingInterface();

  state.currentFile = file;
  state.currentJobId = null;
  state.currentJob = null;
  state.analysisRequested = false;

  uploadCard.classList.add(
    "hidden"
  );

  projectCard.classList.remove(
    "hidden"
  );

  filenameEl.textContent =
    file.name;

  setJobStatus("Uploading");

  setProgress(
    3,
    "Preparing upload…"
  );

  const formData =
    new FormData();

  formData.append(
    "file",
    file,
    file.name
  );

  try {
    const response =
      await fetch(
        "/api/upload",
        {
          method: "POST",
          body: formData,
        }
      );

    const data =
      await parseJsonResponse(
        response
      );

    if (!response.ok) {
      throw new Error(
        getApiError(
          data,
          "Video upload failed."
        )
      );
    }

    if (
      !data ||
      !data.success ||
      !data.job
    ) {
      throw new Error(
        "The server returned an invalid upload response."
      );
    }

    state.currentJobId =
      data.job.id;

    state.currentJob =
      data.job;

    updateJob(
      data.job
    );

    showToast(
      "Video uploaded successfully."
    );

    startPolling(
      data.job.id
    );

  } catch (error) {
    showError(
      getErrorMessage(error)
    );

    setJobStatus("Failed");
  }
}


/* ============================================================
   JOB POLLING
   ============================================================ */

function startPolling(jobId) {
  stopPolling();

  if (!jobId) {
    return;
  }

  pollJob(jobId);
}


function stopPolling() {
  if (state.pollingTimer) {
    window.clearTimeout(
      state.pollingTimer
    );

    state.pollingTimer = null;
  }

  state.pollInProgress = false;
}


async function pollJob(jobId) {
  if (
    !jobId ||
    state.pollInProgress
  ) {
    return;
  }

  state.pollInProgress = true;

  try {
    const response =
      await fetch(
        `/api/jobs/${encodeURIComponent(jobId)}`,
        {
          method: "GET",
          headers: {
            "Accept": "application/json",
          },
          cache: "no-store",
        }
      );

    const data =
      await parseJsonResponse(
        response
      );

    if (!response.ok) {
      throw new Error(
        getApiError(
          data,
          "Could not read processing status."
        )
      );
    }

    if (
      !data ||
      !data.job
    ) {
      throw new Error(
        "The server returned an invalid job response."
      );
    }

    updateJob(
      data.job
    );

    const status =
      String(
        data.job.status || ""
      ).toLowerCase();

    if (
      status === "completed"
    ) {
      stopPolling();

      showToast(
        "Your clips are ready."
      );

      return;
    }

    if (
      status === "failed"
    ) {
      stopPolling();

      showError(
        data.job.error ||
        "Clip processing failed."
      );

      return;
    }

    state.pollInProgress =
      false;

    state.pollingTimer =
      window.setTimeout(
        () => {
          pollJob(jobId);
        },
        1200
      );

  } catch (error) {
    state.pollInProgress =
      false;

    showError(
      getErrorMessage(error)
    );

    setJobStatus("Failed");
  }
}


/* ============================================================
   JOB UI
   ============================================================ */

function updateJob(job) {
  if (!job) {
    return;
  }

  state.currentJob =
    job;

  if (job.id) {
    state.currentJobId =
      job.id;
  }

  if (job.filename) {
    filenameEl.textContent =
      job.filename;
  }

  setJobStatus(
    job.status || "Processing"
  );

  setProgress(
    Number(job.progress) || 0,
    job.message || ""
  );

  if (job.metadata) {
    renderMetadata(
      job.metadata
    );
  }

  if (Array.isArray(job.candidates)) {
    renderCandidates(
      job.candidates
    );
  }

  if (Array.isArray(job.outputs)) {
    renderOutputs(
      job.outputs
    );
  }

  if (
    String(job.status).toLowerCase() ===
    "failed"
  ) {
    showError(
      job.error ||
      "Processing failed."
    );
  }
}


function setJobStatus(status) {
  if (!jobStatus) {
    return;
  }

  jobStatus.textContent =
    formatStatus(status);
}


function setProgress(
  percentage,
  message
) {
  const safePercentage =
    Math.max(
      0,
      Math.min(
        100,
        Number(percentage) || 0
      )
    );

  progressBar.style.width =
    `${safePercentage}%`;

  progressText.textContent =
    `${Math.round(safePercentage)}%`;

  jobMessage.textContent =
    message || "";
}


function formatStatus(status) {
  const value =
    String(status || "")
      .replaceAll("_", " ")
      .trim();

  if (!value) {
    return "Waiting";
  }

  return value
    .charAt(0)
    .toUpperCase() +
    value.slice(1);
}


/* ============================================================
   METADATA
   ============================================================ */

function renderMetadata(metadata) {
  if (!metadataGrid) {
    return;
  }

  const items = [
    {
      label: "Duration",
      value:
        formatDuration(
          metadata.duration
        ),
    },
    {
      label: "Resolution",
      value:
        metadata.width &&
        metadata.height
          ? `${metadata.width} × ${metadata.height}`
          : "Unknown",
    },
    {
      label: "Codec",
      value:
        metadata.codec ||
        "Unknown",
    },
    {
      label: "Frame rate",
      value:
        metadata.fps ||
        "Unknown",
    },
  ];

  metadataGrid.innerHTML =
    items
      .map(
        (item) => `
          <div class="metadata-item">
            <span class="metadata-label">
              ${escapeHtml(item.label)}
            </span>

            <span class="metadata-value">
              ${escapeHtml(item.value)}
            </span>
          </div>
        `
      )
      .join("");

  metadataSection.classList.remove(
    "hidden"
  );
}


/* ============================================================
   CANDIDATES
   ============================================================ */

function renderCandidates(
  candidates
) {
  if (!candidateGrid) {
    return;
  }

  candidateGrid.innerHTML = "";

  if (
    !Array.isArray(candidates) ||
    candidates.length === 0
  ) {
    candidateSection.classList.add(
      "hidden"
    );

    return;
  }

  candidates.forEach(
    (candidate, index) => {
      const item =
        document.createElement(
          "article"
        );

      item.className =
        "candidate";

      const start =
        Number(candidate.start) || 0;

      const end =
        Number(candidate.end) || 0;

      const duration =
        Number(
          candidate.duration
        ) ||
        Math.max(
          0,
          end - start
        );

      const score =
        Number(
          candidate.score
        );

      const safeScore =
        Number.isFinite(score)
          ? Math.round(score)
          : 0;

      item.innerHTML = `
        <div class="candidate-main">

          <strong>
            Moment ${index + 1}
          </strong>

          <small>
            ${formatTime(start)}
            →
            ${formatTime(end)}
            ·
            ${Math.round(duration)}s
          </small>

          <small class="candidate-reason">
            ${escapeHtml(
              candidate.reason ||
              "Potential highlight"
            )}
          </small>

        </div>

        <div class="score">
          ${safeScore}
        </div>
      `;

      candidateGrid.appendChild(
        item
      );
    }
  );

  candidateSection.classList.remove(
    "hidden"
  );
}


/* ============================================================
   GENERATED OUTPUTS
   ============================================================ */

function renderOutputs(outputs) {
  if (!outputGrid) {
    return;
  }

  outputGrid.innerHTML = "";

  if (
    !Array.isArray(outputs) ||
    outputs.length === 0
  ) {
    outputSection.classList.add(
      "hidden"
    );

    return;
  }

  outputs.forEach(
    (output, index) => {
      const item =
        document.createElement(
          "article"
        );

      item.className =
        "output";

      const video =
        document.createElement(
          "video"
        );

      video.controls = true;
      video.preload = "metadata";
      video.playsInline = true;

      const outputUrl =
        sanitizeMediaUrl(
          output.url
        );

      if (outputUrl) {
        video.src =
          outputUrl;
      }

      const info =
        document.createElement(
          "div"
        );

      info.className =
        "output-info";

      const details =
        document.createElement(
          "div"
        );

      const title =
        document.createElement(
          "strong"
        );

      title.textContent =
        output.filename ||
        `Clip ${index + 1}`;

      const metadata =
        document.createElement(
          "small"
        );

      const duration =
        Number(
          output.duration
        );

      const dimensions =
        output.width &&
        output.height
          ? `${output.width}×${output.height}`
          : "9:16";

      metadata.textContent =
        `${Number.isFinite(duration) ? Math.round(duration) : "—"}s · ${dimensions}`;

      details.appendChild(
        title
      );

      details.appendChild(
        metadata
      );

      const download =
        document.createElement(
          "a"
        );

      download.textContent =
        "Download";

      download.href =
        outputUrl || "#";

      download.download =
        output.filename ||
        `clip-${index + 1}.mp4`;

      if (!outputUrl) {
        download.removeAttribute(
          "href"
        );
      }

      info.appendChild(
        details
      );

      info.appendChild(
        download
      );

      item.appendChild(
        video
      );

      item.appendChild(
        info
      );

      outputGrid.appendChild(
        item
      );
    }
  );

  outputSection.classList.remove(
    "hidden"
  );
}


/* ============================================================
   AI ANALYSIS REQUEST
   ============================================================ */

function initializeAnalysis() {
  if (!analyzeButton) {
    return;
  }

  analyzeButton.addEventListener(
    "click",
    requestAnalysis
  );

  if (clipPrompt) {
    clipPrompt.addEventListener(
      "keydown",
      (event) => {
        if (
          event.key === "Enter" &&
          !event.shiftKey
        ) {
          event.preventDefault();

          requestAnalysis();
        }
      }
    );
  }
}


async function requestAnalysis() {
  /*
   * The first processing backend already analyzes candidate
   * windows automatically.
   *
   * This request is prepared for the upgraded Clip_ S
   * intelligence layer. If the backend does not expose
   * /api/analyze yet, we keep the existing processing flow
   * instead of breaking the application.
   */

  if (!state.currentJobId) {
    showToast(
      "Upload a video first."
    );

    return;
  }

  const prompt =
    clipPrompt?.value.trim() || "";

  if (!prompt) {
    showToast(
      "Tell Clip_ S what kind of moments you want."
    );

    clipPrompt?.focus();

    return;
  }

  if (prompt.length > 500) {
    showToast(
      "Your request is too long."
    );

    return;
  }

  if (state.analysisRequested) {
    return;
  }

  state.analysisRequested =
    true;

  const originalText =
    analyzeButton.textContent;

  analyzeButton.disabled =
    true;

  analyzeButton.textContent =
    "Analyzing…";

  clearError();

  try {
    const response =
      await fetch(
        "/api/analyze",
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",

            "Accept":
              "application/json",
          },

          body: JSON.stringify({
            job_id:
              state.currentJobId,

            prompt,
          }),
        }
      );

    const data =
      await parseJsonResponse(
        response
      );

    if (!response.ok) {
      /*
       * The route may not exist in the first backend layer.
       * That is not allowed to break the rest of Clip_ S.
       */
      if (
        response.status === 404
      ) {
        showToast(
          "AI search will become active when the intelligence worker is connected."
        );

        return;
      }

      throw new Error(
        getApiError(
          data,
          "AI analysis failed."
        )
      );
    }

    if (data.job) {
      updateJob(
        data.job
      );
    }

    if (Array.isArray(data.candidates)) {
      renderCandidates(
        data.candidates
      );
    }

    showToast(
      "Clip_ S finished analyzing the request."
    );

  } catch (error) {
    showError(
      getErrorMessage(error)
    );

  } finally {
    state.analysisRequested =
      false;

    analyzeButton.disabled =
      false;

    analyzeButton.textContent =
      originalText;
  }
}


/* ============================================================
   PROMPT SUGGESTIONS
   ============================================================ */

function initializeSuggestions() {
  const suggestions =
    document.querySelectorAll(
      ".suggestion"
    );

  suggestions.forEach(
    (button) => {
      button.addEventListener(
        "click",
        () => {
          const prompt =
            button.dataset.prompt ||
            "";

          if (clipPrompt) {
            clipPrompt.value =
              prompt;

            clipPrompt.focus();
          }
        }
      );
    }
  );
}


/* ============================================================
   NEW PROJECT
   ============================================================ */

function initializeProjectControls() {
  if (!newProjectButton) {
    return;
  }

  newProjectButton.addEventListener(
    "click",
    resetProject
  );
}


function resetProject() {
  stopPolling();

  state.currentJobId = null;
  state.currentFile = null;
  state.currentJob = null;
  state.analysisRequested = false;

  if (fileInput) {
    fileInput.value = "";
  }

  if (clipPrompt) {
    clipPrompt.value = "";
  }

  filenameEl.textContent =
    "Video";

  setJobStatus(
    "Waiting"
  );

  setProgress(
    0,
    "Waiting for video…"
  );

  clearError();

  metadataSection?.classList.add(
    "hidden"
  );

  candidateSection?.classList.add(
    "hidden"
  );

  outputSection?.classList.add(
    "hidden"
  );

  if (metadataGrid) {
    metadataGrid.innerHTML = "";
  }

  if (candidateGrid) {
    candidateGrid.innerHTML = "";
  }

  if (outputGrid) {
    outputGrid.innerHTML = "";
  }

  projectCard.classList.add(
    "hidden"
  );

  uploadCard.classList.remove(
    "hidden"
  );

  switchSection(
    "create"
  );
}


/* ============================================================
   PROCESSING RESET
   ============================================================ */

function resetProcessingInterface() {
  clearError();

  metadataSection?.classList.add(
    "hidden"
  );

  candidateSection?.classList.add(
    "hidden"
  );

  outputSection?.classList.add(
    "hidden"
  );

  if (metadataGrid) {
    metadataGrid.innerHTML = "";
  }

  if (candidateGrid) {
    candidateGrid.innerHTML = "";
  }

  if (outputGrid) {
    outputGrid.innerHTML = "";
  }

  setProgress(
    0,
    "Preparing video…"
  );

  setJobStatus(
    "Uploading"
  );
}


/* ============================================================
   ERROR HANDLING
   ============================================================ */

function showError(message) {
  if (!errorBox) {
    return;
  }

  errorBox.textContent =
    message ||
    "Something went wrong.";

  errorBox.classList.remove(
    "hidden"
  );
}


function clearError() {
  if (!errorBox) {
    return;
  }

  errorBox.textContent = "";

  errorBox.classList.add(
    "hidden"
  );
}


/* ============================================================
   TOAST
   ============================================================ */

let toastTimer = null;

function showToast(message) {
  if (!toast) {
    return;
  }

  toast.textContent =
    message;

  toast.classList.remove(
    "hidden"
  );

  if (toastTimer) {
    window.clearTimeout(
      toastTimer
    );
  }

  toastTimer =
    window.setTimeout(
      () => {
        toast.classList.add(
          "hidden"
        );
      },
      3200
    );
}


/* ============================================================
   API HELPERS
   ============================================================ */

async function parseJsonResponse(
  response
) {
  const contentType =
    response.headers.get(
      "content-type"
    ) || "";

  if (
    contentType.includes(
      "application/json"
    )
  ) {
    return response.json();
  }

  const text =
    await response.text();

  return {
    detail:
      text ||
      `HTTP ${response.status}`,
  };
}


function getApiError(
  data,
  fallback
) {
  if (!data) {
    return fallback;
  }

  if (
    typeof data.detail ===
    "string"
  ) {
    return data.detail;
  }

  if (
    typeof data.error ===
    "string"
  ) {
    return data.error;
  }

  if (
    typeof data.message ===
    "string"
  ) {
    return data.message;
  }

  return fallback;
}


function getErrorMessage(error) {
  if (
    error &&
    typeof error.message ===
    "string"
  ) {
    return error.message;
  }

  return "Something went wrong.";
}


/* ============================================================
   FORMATTING
   ============================================================ */

function formatTime(seconds) {
  const total =
    Math.max(
      0,
      Math.floor(
        Number(seconds) || 0
      )
    );

  const minutes =
    Math.floor(
      total / 60
    );

  const remainingSeconds =
    String(
      total % 60
    ).padStart(
      2,
      "0"
    );

  return `${minutes}:${remainingSeconds}`;
}


function formatDuration(seconds) {
  const value =
    Number(seconds);

  if (
    !Number.isFinite(value) ||
    value < 0
  ) {
    return "Unknown";
  }

  if (value < 60) {
    return `${Math.round(value)} sec`;
  }

  const minutes =
    Math.floor(
      value / 60
    );

  const secondsRemaining =
    Math.round(
      value % 60
    );

  return `${minutes}m ${secondsRemaining}s`;
}


/* ============================================================
   SECURITY / HTML ESCAPING
   ============================================================ */

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll(
      "&",
      "&amp;"
    )
    .replaceAll(
      "<",
      "&lt;"
    )
    .replaceAll(
      ">",
      "&gt;"
    )
    .replaceAll(
      '"',
      "&quot;"
    )
    .replaceAll(
      "'",
      "&#039;"
    );
}


function sanitizeMediaUrl(url) {
  if (
    typeof url !== "string" ||
    !url.trim()
  ) {
    return "";
  }

  const trimmed =
    url.trim();

  /*
   * Clip_ S media should normally come
   * from its own application.
   *
   * Allow same-origin relative URLs.
   */
  if (
    trimmed.startsWith("/")
  ) {
    return trimmed;
  }

  /*
   * Do not allow javascript:, data:,
   * blob: or other unexpected protocols
   * to become media/download URLs.
   */
  try {
    const parsed =
      new URL(
        trimmed,
        window.location.origin
      );

    if (
      parsed.origin ===
      window.location.origin
    ) {
      return (
        parsed.pathname +
        parsed.search +
        parsed.hash
      );
    }

  } catch {
    return "";
  }

  return "";
}


/* ============================================================
   PAGE SAFETY
   ============================================================ */

window.addEventListener(
  "beforeunload",
  () => {
    stopPolling();
  }
);


/* ============================================================
   DEBUG ACCESS
   ============================================================ */

window.ClipS = {
  getState() {
    return {
      ...state,
    };
  },

  reset() {
    resetProject();
  },

  refreshStatus() {
    return checkServer();
  },
};

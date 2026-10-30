// Interactive Terminal Tabs
function switchTab(tabId) {
  // Update buttons
  const buttons = document.querySelectorAll('.tab-btn');
  buttons.forEach(btn => {
    if (btn.getAttribute('data-tab') === tabId) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  // Update panels
  const panels = document.querySelectorAll('.tab-content');
  panels.forEach(panel => {
    if (panel.id === tabId) {
      panel.classList.add('active');
    } else {
      panel.classList.remove('active');
    }
  });
}

// OS Quickstart Tabs
function switchOsTab(osId) {
  const buttons = document.querySelectorAll('.os-tab');
  buttons.forEach(btn => {
    if (btn.getAttribute('data-os') === osId) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  const panels = document.querySelectorAll('.os-tab-content');
  panels.forEach(panel => {
    if (panel.id === osId) {
      panel.classList.add('active');
    } else {
      panel.classList.remove('active');
    }
  });
}

// Clipboard Copy Helper
function copyCode(btn, text) {
  navigator.clipboard.writeText(text).then(() => {
    const originalHtml = btn.innerHTML;
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg> Copied!`;
    btn.style.color = '#34d399';
    btn.style.borderColor = '#10b981';
    
    setTimeout(() => {
      btn.innerHTML = originalHtml;
      btn.style.color = '';
      btn.style.borderColor = '';
    }, 2000);
  }).catch(err => {
    console.error('Failed to copy: ', err);
  });
}

// Mobile Menu Toggle
function toggleMobileMenu() {
  const menu = document.getElementById('mobileMenu');
  if (menu) {
    menu.classList.toggle('open');
  }
}

// Live TOTP countdown simulation in hero demo
let totpSeconds = 30 - (Math.floor(Date.now() / 1000) % 30);
function updateTotpCountdown() {
  const totpTimerEl = document.getElementById('liveTotpTimer');
  if (totpTimerEl) {
    totpTimerEl.textContent = `(${totpSeconds}s remaining)`;
  }
  totpSeconds--;
  if (totpSeconds < 0) {
    totpSeconds = 29;
    const totpCodeEl = document.getElementById('liveTotpCode');
    if (totpCodeEl) {
      // Generate a mock code refresh
      const randomCode = Math.floor(100000 + Math.random() * 900000);
      totpCodeEl.textContent = `${String(randomCode).slice(0, 3)} ${String(randomCode).slice(3)}`;
    }
  }
}

// Tech Badge Explainer Modal Knowledge Base
const TECH_SPECS = {
  'argon2id': {
    category: 'Cryptographic KDF Engine',
    title: 'Argon2id (64MB / 3-iter)',
    subtitle: 'Winner of Password Hashing Competition (RFC 9106)',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    what: 'Argon2id is a hybrid key derivation function combining <strong>Argon2d</strong> (resistant to GPU cracking) and <strong>Argon2i</strong> (hardened against side-channel cache attacks). It takes your human master password and deliberately burns memory and CPU cycles to derive high-entropy 256-bit cryptographic keys.',
    why: 'Legacy password managers still use PBKDF2 with low iteration counts. Dedicated ASIC miners and modern consumer GPUs can compute billions of PBKDF2 hashes per second. Argon2id forces the cracker to allocate <strong>64 megabytes of dedicated RAM per guess</strong>, creating an economic bottleneck that destroys GPU parallelism.',
    how: 'SCM passes your master password through Argon2id with <code>memory_cost = 64 MB</code>, <code>time_cost = 3 iterations</code>, <code>parallelism = 4 threads</code>, and a 16-byte cryptographically secure OS random salt (<code>os.urandom(16)</code>). It derives a 64-byte buffer: 32 bytes for the verifier, and 32 bytes for the Key Encryption Key (KEK).',
    code: `# SCM Key Derivation Pipeline (RFC 9106)
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

kdf = Argon2id(
    salt=os.urandom(16),
    length=64,             # 32B Verifier + 32B KEK
    iterations=3,          # Time cost
    lanes=4,               # Parallelism
    memory_cost=65536      # 64 MB dedicated RAM per evaluation
)
key_material = kdf.derive(master_password.encode('utf-8'))`
  },
  'envelope': {
    category: 'Cryptographic Architecture',
    title: 'Two-Tier Envelope Encryption (KEK/DEK)',
    subtitle: 'KMS-Style Separation of Key Management & Bulk Data Protection',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>',
    what: 'Envelope encryption is a hierarchical security design where secret data is encrypted under a unique, randomized <strong>Data Encryption Key (DEK)</strong>, which is itself encrypted ("wrapped") under a <strong>Key Encryption Key (KEK)</strong> derived from the master password.',
    why: 'In traditional single-key password vaults, changing your master password forces re-encrypting the entire vault row by row, posing catastrophic risk of corruption if interrupted. Furthermore, exposing the master KDF key in a memory attack could immediately compromise the entire database.',
    how: 'SCM decouples the master key from vault records. The DEK is generated once with high-grade OS randomness. Your master password derives the KEK, which wraps the DEK via <strong>AES-256-GCM</strong>. When you rotate your master password, SCM only re-wraps the 32-byte DEK envelope in less than 1ms without touching a single encrypted credential record.',
    code: `+-----------------------------------------------------------+
| User Master Password  -->  Argon2id KDF  -->  KEK (32B)   |
+-----------------------------------------------------------+
                              |
                              v  AES-256-GCM Unwrap
+-----------------------------------------------------------+
| Encrypted Envelope  ----->  Data Encryption Key (DEK)     |
+-----------------------------------------------------------+
                              |
        +---------------------+---------------------+
        v Row-Level AES-GCM                         v HMAC Blind Index
   Record Payloads                             Fast O(1) Searches`
  },
  'sqlite-wal': {
    category: 'Storage & ACID Durability',
    title: 'SQLite WAL Mode & Blind Indexing',
    subtitle: 'Zero-Knowledge Atomic Transaction Engine',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7v10c0 2 1.5 3 3.5 3h9c2 0 3.5-1 3.5-3V7c0-2-1.5-3-3.5-3h-9C5.5 4 4 5 4 7z"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/></svg>',
    what: 'SQLite in <strong>Write-Ahead Logging (WAL)</strong> mode writes changes to a dedicated journal before merging them into the main database file. Paired with <strong>HMAC-SHA256 Blind Indexing</strong>, SCM queries records in zero-knowledge fashion without revealing plaintext names or service identifiers.',
    why: 'Traditional JSON flat files rewrite the entire vault to disk on every single edit—risking silent truncations, lock contention, and SSD fragmentation during crashes. In addition, indexing plaintext service names in an encrypted database leaks metadata (e.g. knowing you have accounts on specific banks or exchanges).',
    how: 'SCM configures SQLite with <code>PRAGMA journal_mode=WAL</code> and <code>PRAGMA synchronous=NORMAL</code>, guaranteeing atomic ACID durability across hard power cuts. Record names are hashed into an uninvertible Blind Index using <code>HMAC-SHA256(Service_Name, Blind_Pepper)</code>. Exact searches run at O(1) speed without ever decrypting neighboring records.',
    code: `-- Zero-Knowledge Row Schema & WAL Configuration
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE credentials (
    blind_index   TEXT PRIMARY KEY,  -- HMAC-SHA256(service_name, pepper)
    nonce         BLOB NOT NULL,     -- 96-bit unique AES-GCM IV
    ciphertext    BLOB NOT NULL,     -- AES-256-GCM encrypted payload
    auth_tag      BLOB NOT NULL,     -- 128-bit authentication tag
    updated_at    INTEGER NOT NULL
);`
  },
  'totp': {
    category: 'Multi-Factor Authentication',
    title: 'RFC 6238 TOTP 2FA Engine',
    subtitle: 'Sovereign Time-Based One-Time Password Token Generation',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    what: '<strong>RFC 6238</strong> is the open cryptographic standard for Time-based One-Time Passwords (TOTP). It converts a shared secret seed and the current Unix timestamp into a dynamic 6-digit or 8-digit verification code that rotates every 30 seconds.',
    why: 'Relying on proprietary cloud 2FA apps (Authy, Google Authenticator) ties your two-factor security to phone ecosystems and remote syncing servers that can lock you out or suffer SIM-swap and cloud recovery compromises.',
    how: 'SCM natively ingests <code>otpauth://totp/</code> URIs, QR codes, or Base32 secret seeds. It evaluates <code>HMAC-SHA1(Secret, Floor(UnixTime / 30))</code> entirely in-memory and displays real-time countdown clocks in both the CLI and Desktop UI, with zero telemetry or network calls.',
    code: `# RFC 6238 Standard Dynamic Truncation
time_counter = struct.pack(">Q", int(time.time()) // 30)
hmac_digest = hmac.new(base32_secret, time_counter, hashlib.sha1).digest()
offset = hmac_digest[-1] & 0x0F
binary_code = struct.unpack(">I", hmac_digest[offset:offset+4])[0] & 0x7FFFFFFF
totp_token = str(binary_code % (10 ** 6)).zfill(6)`
  },
  'hibp': {
    category: 'Threat Intelligence & Auditing',
    title: 'HIBP k-Anonymity Leak Check',
    subtitle: 'Mathematical Privacy for Compromised Credential Auditing',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/></svg>',
    what: '<strong>k-Anonymity</strong> is a formal privacy model that guarantees individual records cannot be distinguished from a group of at least <em>k</em> candidates. Used with Troy Hunt\'s HaveIBeenPwned database of billions of breached passwords, it checks if your credentials have appeared in known breaches.',
    why: 'Checking passwords against a leak database normally requires sending the password (or its full hash) to a remote server, introducing a massive surveillance and man-in-the-middle threat.',
    how: 'SCM hashes your password locally via <code>SHA-1(password)</code>. It sends ONLY the first 5 hexadecimal characters (20 bits of entropy) to the HIBP API. The API returns a bucket of ~500 matching hash suffixes. SCM matches the remaining 35 characters locally in memory. The remote server never learns your password, full hash, or identity.',
    code: `# SCM k-Anonymity HIBP Verification
sha1_hash = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
prefix, suffix = sha1_hash[:5], sha1_hash[5:]

# Query only the 5-char prefix over HTTPS
# Server returns ~500 hashes sharing this prefix
response = requests.get(f"https://api.pwnedpasswords.com/range/{prefix}")

# Matching occurs purely locally on your workstation
is_compromised = any(line.startswith(suffix) for line in response.text.splitlines())`
  },
  'secure-buffer': {
    category: 'Runtime Memory Defense',
    title: 'SecureBuffer Memory Zeroing',
    subtitle: 'Anti-Forensic Ephemeral Buffer Sanitation',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    what: 'In standard high-level programming languages like Python or JavaScript, strings are <em>immutable</em>. When you discard a password variable, it remains resident in unmanaged process memory until arbitrary garbage collection cycles.',
    why: 'Memory scraping malware, crash dump logs, cold-boot memory dumps, or swap files on unencrypted hard disks can effortlessly carve plaintext secrets long after you closed or locked your application.',
    how: 'SCM wraps all cryptographic keys and unlocked credentials in dedicated <code>SecureBuffer</code> bytearrays. Upon user lock or the automatic 60-second idle countdown, SCM executes an explicit C-style overwrite loop, replacing every byte with <code>0x00</code> and releasing the buffer before unsetting references.',
    code: `class SecureBuffer:
    def __init__(self, data: bytes):
        self._buf = bytearray(data)

    def zeroize(self):
        """Explicit C-level memory zeroing to sanitize RAM."""
        if self._buf is not None:
            for i in range(len(self._buf)):
                self._buf[i] = 0  # Overwrite byte with zero
            self._buf = None

    def __del__(self):
        self.zeroize()`
  },
  'zero-clipboard': {
    category: 'Operating System Privacy',
    title: 'Zero-Trace OS Clipboard',
    subtitle: 'Hardware-Level OS History Exclusion & Auto-Erasure',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
    what: 'Modern operating systems automatically record every clipboard copy into persistent cloud-synced databases (Windows Clipboard History Win+V, macOS universal clipboard, KDE/GNOME clipboard daemons). Zero-Trace OS Clipboard marks copied secrets as sensitive private data.',
    why: 'Standard clipboard copy leaves passwords vulnerable to any untrusted background process, clipboard manager extension, or cloud sync to personal Microsoft/Apple accounts.',
    how: 'When copying from SCM, it registers native OS privacy hints: <code>ClipboardViewerIgnore</code> and <code>ExcludeClipboardContentFromMonitorProcessing</code> on Windows, and <code>org.nspasteboard.ConcealedType</code> on macOS. SCM then starts a dedicated background thread that overwrites the system clipboard with null characters after exactly 30 seconds.',
    code: `# Windows Win32 API Privacy Format Flags
CF_CLIPBOARD_VIEWER_IGNORE = user32.RegisterClipboardFormatW("ClipboardViewerIgnore")
CF_EXCLUDE_FROM_MONITOR = user32.RegisterClipboardFormatW(
    "ExcludeClipboardContentFromMonitorProcessing"
)
# Register flags on OpenClipboard handle to prevent Windows 10/11 history logging
user32.SetClipboardData(CF_CLIPBOARD_VIEWER_IGNORE, 0)
user32.SetClipboardData(CF_EXCLUDE_FROM_MONITOR, 0)

# Launch 30s auto-erase countdown
threading.Thread(target=auto_erase_clipboard, args=(30,), daemon=True).start()`
  },
  'cross-platform': {
    category: 'System Portability & Security',
    title: 'Cross-Platform Native Vault',
    subtitle: 'Deterministic Uniformity Across Windows, macOS & Linux',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
    what: 'A unified codebase architecture delivering identically verified cryptographic guarantees, atomic storage, and dual GUI/CLI interfaces regardless of host operating system.',
    why: 'Security software frequently features platform disparity—Windows builds rely on proprietary DPAPI blobs, while Linux ports lack UI polish or safe clipboard clearing. Vault formats often lock users into a single operating system vendor.',
    how: 'SCM uses standard Python 3.12+ with standard POSIX file permissions (<code>chmod 0600</code>) on Unix, Win32 DACL isolation on Windows, and atomic file replacements (<code>os.replace</code>). Your vault file (<code>vault.scmdb</code>) can be moved seamlessly between Windows 11, macOS Sequoia, and headless Arch Linux without transformation.',
    code: `~/.simpleCredentialManager/
├── vault.scmdb          # AES-256-GCM + SQLite WAL payload (Mode 0600)
├── vault.scmdb-wal      # Fast atomic WAL write log
└── vault.scmdb-shm      # Shared memory index
~/.config/.simpleCredentialManager/
├── .metadata            # Argon2id salt, verifier, DEK envelope, lockout state
└── .scm.audit.log       # Monotonic JSONL tamper-evident event log`
  }
};

// Modal Controller State
let currentTechKey = 'argon2id';
const techKeyOrder = ['argon2id', 'envelope', 'sqlite-wal', 'totp', 'hibp', 'secure-buffer', 'zero-clipboard', 'cross-platform'];

function openTechModal(techKey) {
  const spec = TECH_SPECS[techKey];
  if (!spec) return;

  currentTechKey = techKey;
  const modal = document.getElementById('techModal');
  const catEl = document.getElementById('modalSpecCategory');
  const titleEl = document.getElementById('modalTitle');
  const subEl = document.getElementById('modalSubtitle');
  const iconEl = document.getElementById('modalIcon');
  const whatEl = document.getElementById('modalWhat');
  const whyEl = document.getElementById('modalWhy');
  const howEl = document.getElementById('modalHow');
  const codeWrap = document.getElementById('modalCodeSnippet');
  const codeText = document.getElementById('modalCodeText');

  if (catEl) catEl.textContent = spec.category;
  if (titleEl) titleEl.textContent = spec.title;
  if (subEl) subEl.textContent = spec.subtitle;
  if (iconEl) iconEl.innerHTML = spec.icon;
  if (whatEl) whatEl.innerHTML = spec.what;
  if (whyEl) whyEl.innerHTML = spec.why;
  if (howEl) howEl.innerHTML = spec.how;

  if (spec.code && codeWrap && codeText) {
    codeText.textContent = spec.code;
    codeWrap.style.display = 'block';
  } else if (codeWrap) {
    codeWrap.style.display = 'none';
  }

  // Update navigation button states
  const currentIndex = techKeyOrder.indexOf(techKey);
  const prevBtn = document.getElementById('modalPrevBtn');
  const nextBtn = document.getElementById('modalNextBtn');

  if (prevBtn) {
    const prevIndex = (currentIndex - 1 + techKeyOrder.length) % techKeyOrder.length;
    prevBtn.setAttribute('title', TECH_SPECS[techKeyOrder[prevIndex]].title);
  }
  if (nextBtn) {
    const nextIndex = (currentIndex + 1) % techKeyOrder.length;
    nextBtn.setAttribute('title', TECH_SPECS[techKeyOrder[nextIndex]].title);
  }

  // Open overlay
  if (modal) {
    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    
    // Focus close button for accessibility
    const closeBtn = modal.querySelector('.tech-modal-close');
    if (closeBtn) closeBtn.focus();
  }
}

function closeTechModal() {
  const modal = document.getElementById('techModal');
  if (modal) {
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');

    // Return focus to the trigger badge
    const activeBadge = document.querySelector(`.tech-badge[data-tech="${currentTechKey}"]`);
    if (activeBadge) activeBadge.focus();
  }
}

function navigateTechModal(direction) {
  const currentIndex = techKeyOrder.indexOf(currentTechKey);
  let nextIndex = direction === 'next' ? currentIndex + 1 : currentIndex - 1;
  if (nextIndex >= techKeyOrder.length) nextIndex = 0;
  if (nextIndex < 0) nextIndex = techKeyOrder.length - 1;
  openTechModal(techKeyOrder[nextIndex]);
}

function copyModalCode() {
  const codeEl = document.getElementById('modalCodeText');
  const btn = document.getElementById('modalCopyCodeBtn');
  if (!codeEl || !btn) return;

  copyCode(btn, codeEl.textContent);
}

// Global Event Listeners for Tech Badges and Modal
document.addEventListener('DOMContentLoaded', () => {
  // Bind click & keyboard handlers to all tech badges
  const badges = document.querySelectorAll('.tech-badge[data-tech]');
  badges.forEach(badge => {
    badge.addEventListener('click', (e) => {
      e.preventDefault();
      const techKey = badge.getAttribute('data-tech');
      if (techKey) openTechModal(techKey);
    });

    badge.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const techKey = badge.getAttribute('data-tech');
        if (techKey) openTechModal(techKey);
      }
    });
  });

  // Modal close handlers (backdrop & close buttons)
  const closeElements = document.querySelectorAll('[data-close-modal]');
  closeElements.forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      closeTechModal();
    });
  });

  // Prev / Next modal navigation buttons
  const prevBtn = document.getElementById('modalPrevBtn');
  const nextBtn = document.getElementById('modalNextBtn');
  if (prevBtn) {
    prevBtn.addEventListener('click', () => navigateTechModal('prev'));
  }
  if (nextBtn) {
    nextBtn.addEventListener('click', () => navigateTechModal('next'));
  }

  // Keyboard accessibility: ESC to close, Left/Right arrows to navigate
  document.addEventListener('keydown', (e) => {
    const modal = document.getElementById('techModal');
    if (!modal || !modal.classList.contains('active')) return;

    if (e.key === 'Escape') {
      e.preventDefault();
      closeTechModal();
    } else if (e.key === 'ArrowRight') {
      navigateTechModal('next');
    } else if (e.key === 'ArrowLeft') {
      navigateTechModal('prev');
    }
  });
});

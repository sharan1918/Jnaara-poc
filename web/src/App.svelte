<script lang="ts">
  import { onMount } from 'svelte';
  import {
    Sun,
    Moon,
    Upload,
    Send,
    RefreshCw,
    AlertTriangle,
    CheckCircle2,
    Database,
    Layers,
    ShieldCheck,
    Trash2,
    History,
    Search,
    FileText,
    Sparkles,
    ChevronRight,
    X
  } from 'lucide-svelte';

  // Types
  interface Belief {
    id: str;
    entity: str;
    attribute: str;
    value: str;
    confidence: number;
    supporting_fact_ids: string[];
    contradicting_fact_ids: string[];
    last_updated: string;
    version: number;
    status: string;
  }

  interface Conflict {
    id: string;
    conflict_type: string;
    entity: string;
    attribute: string;
    existing_belief_id: string;
    incoming_claim_id: string;
    severity: string;
    description: string;
    detected_at: string;
    resolution?: {
      winner: string;
      strategy_used: string;
      rationale: string;
      confidence_delta: number;
    };
  }

  interface Stats {
    total_facts: number;
    active_beliefs: number;
    total_conflicts: number;
    active_strategy: string;
    available_strategies: string[];
    primary_llm: string;
    secondary_llm: string;
  }

  interface FactProcessResult {
    fact_id: string;
    skipped: boolean;
    claims_count: number;
    claims: Array<{
      id: string;
      entity: string;
      attribute: string;
      value: string;
      claim_type: string;
      confidence: number;
    }>;
    decisions: Array<{
      action: string;
      reason: string;
      tier: string;
    }>;
    conflicts: Array<{
      description: string;
      conflict_type: string;
      resolution?: {
        winner: string;
        strategy_used: string;
        rationale: string;
      };
    }>;
  }

  interface ProvenanceData {
    belief: Belief;
    history: Array<{
      version: number;
      old_value: string | null;
      new_value: string;
      old_confidence: number | null;
      new_confidence: number;
      changed_by_fact_id: string;
      reason: string | null;
      changed_at: string;
    }>;
    supporting_facts: any[];
    contradicting_facts: any[];
    conflicts: any[];
    decisions: any[];
  }

  // State
  let theme = $state<'dark' | 'light'>('dark');
  let stats = $state<Stats>({
    total_facts: 0,
    active_beliefs: 0,
    total_conflicts: 0,
    active_strategy: 'recency',
    available_strategies: ['recency', 'corroboration'],
    primary_llm: 'groq',
    secondary_llm: 'gemini'
  });

  let activeTab = $state<'single' | 'upload'>('single');
  let activeView = $state<'beliefs' | 'conflicts'>('beliefs');

  // Single Fact Input
  let factContent = $state('');
  let factSource = $state('Analyst Report');
  let factReliability = $state<'high' | 'medium' | 'low'>('high');
  let isSubmitting = $state(false);
  let liveResult = $state<FactProcessResult | null>(null);

  // File Upload
  let uploadFile = $state<File | null>(null);
  let uploadSequence = $state<string>('');
  let isUploading = $state(false);
  let uploadMessage = $state<string | null>(null);
  let dragOver = $state(false);

  // Knowledge Explorer
  let beliefs = $state<Belief[]>([]);
  let conflicts = $state<Conflict[]>([]);
  let searchQuery = $state('');
  let isLoadingData = $state(false);

  // Provenance Modal
  let activeProvenance = $state<ProvenanceData | null>(null);
  let isProvenanceLoading = $state(false);

  // Reset Confirmation Modal
  let showResetModal = $state(false);

  // Presets
  const presets = [
    {
      label: '1. Initial Revenue ($480M)',
      text: 'NovaTech Inc. reported Q4 2024 revenue of $480M, representing 32% year-over-year growth.',
      source: 'NovaTech Q4 Earnings Release',
      reliability: 'high' as const
    },
    {
      label: '2. Restatement Contradiction ($412M)',
      text: 'NovaTech Inc. issued a restatement: Q4 2024 revenue was $412M, not $480M as previously reported.',
      source: 'SEC Filing (8-K)',
      reliability: 'high' as const
    },
    {
      label: '3. Strategic Acquisition ($3.5B)',
      text: 'Solaris Energy announced a definitive agreement to acquire WindCo for $3.5B in all-cash transaction.',
      source: 'PR Newswire',
      reliability: 'high' as const
    },
    {
      label: '4. Rumored Price ($3.2B)',
      text: 'Anonymous insiders claim Solaris Energy negotiated the WindCo buyout price down to $3.2B.',
      source: 'TechBlog Leaks',
      reliability: 'low' as const
    }
  ];

  function applyPreset(preset: typeof presets[0]) {
    factContent = preset.text;
    factSource = preset.source;
    factReliability = preset.reliability;
  }

  function toggleTheme() {
    theme = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('jnaara_theme', theme);
  }

  async function fetchStats() {
    try {
      const res = await fetch('/api/stats');
      if (res.ok) {
        stats = await res.json();
      }
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  }

  async function fetchBeliefs() {
    try {
      isLoadingData = true;
      const url = searchQuery
        ? `/api/beliefs?entity=${encodeURIComponent(searchQuery)}`
        : '/api/beliefs';
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        beliefs = data.beliefs;
      }
    } catch (err) {
      console.error('Failed to fetch beliefs:', err);
    } finally {
      isLoadingData = false;
    }
  }

  async function fetchConflicts() {
    try {
      const url = searchQuery
        ? `/api/conflicts?entity=${encodeURIComponent(searchQuery)}`
        : '/api/conflicts';
      const res = await fetch(url);
      if (res.ok) {
        conflicts = await res.json();
      }
    } catch (err) {
      console.error('Failed to fetch conflicts:', err);
    }
  }

  async function refreshAll() {
    await Promise.all([fetchStats(), fetchBeliefs(), fetchConflicts()]);
  }

  async function handleStrategyChange(newStrat: string) {
    try {
      const res = await fetch('/api/strategy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy: newStrat })
      });
      if (res.ok) {
        stats.active_strategy = newStrat;
        await refreshAll();
      }
    } catch (err) {
      console.error('Failed to switch strategy:', err);
    }
  }

  async function submitSingleFact() {
    if (!factContent.trim() || isSubmitting) return;

    try {
      isSubmitting = true;
      liveResult = null;

      const res = await fetch('/api/facts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: factContent.trim(),
          source: factSource.trim() || 'User Input',
          source_reliability: factReliability
        })
      });

      if (res.ok) {
        liveResult = await res.json();
        factContent = '';
        await refreshAll();
      } else {
        const errorData = await res.json();
        alert(`Error: ${errorData.message || 'Failed to submit fact'}`);
      }
    } catch (err: any) {
      alert(`Network error: ${err.message}`);
    } finally {
      isSubmitting = false;
    }
  }

  async function handleFileUpload() {
    if (!uploadFile || isUploading) return;

    try {
      isUploading = true;
      uploadMessage = 'Uploading and evaluating facts dataset...';

      const formData = new FormData();
      formData.append('file', uploadFile);

      const url = uploadSequence
        ? `/api/facts/upload?sequence=${encodeURIComponent(uploadSequence)}`
        : '/api/facts/upload';

      const res = await fetch(url, {
        method: 'POST',
        body: formData
      });

      if (res.ok) {
        const data = await res.json();
        uploadMessage = `Successfully processed ${data.total_processed} facts (${data.total_claims} claims, ${data.total_conflicts} conflicts detected).`;
        uploadFile = null;
        await refreshAll();
      } else {
        const errorData = await res.json();
        uploadMessage = `Error: ${errorData.detail || errorData.message || 'Upload failed'}`;
      }
    } catch (err: any) {
      uploadMessage = `Network error: ${err.message}`;
    } finally {
      isUploading = false;
    }
  }

  async function openProvenance(beliefId: string) {
    try {
      isProvenanceLoading = true;
      activeProvenance = null;
      const res = await fetch(`/api/beliefs/${beliefId}/provenance`);
      if (res.ok) {
        activeProvenance = await res.json();
      }
    } catch (err) {
      console.error('Failed to fetch provenance:', err);
    } finally {
      isProvenanceLoading = false;
    }
  }

  async function executeReset() {
    try {
      const res = await fetch('/api/reset', { method: 'POST' });
      if (res.ok) {
        showResetModal = false;
        liveResult = null;
        await refreshAll();
      }
    } catch (err) {
      console.error('Failed to reset:', err);
    }
  }

  function onKeyDown(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      submitSingleFact();
    }
  }

  onMount(() => {
    const savedTheme = (localStorage.getItem('jnaara_theme') as 'dark' | 'light') || 'dark';
    theme = savedTheme;
    document.documentElement.setAttribute('data-theme', theme);
    refreshAll();
  });
</script>

<svelte:window onkeydown={onKeyDown} />

<div class="app-container">
  <!-- Header Bar -->
  <header class="header">
    <div class="brand-section">
      <div class="brand-icon">
        <Database size={22} />
      </div>
      <div>
        <div class="brand-title">
          <span>JNAARA</span>
          <span class="pill pill-primary">POC</span>
        </div>
        <div class="brand-subtitle">Deterministic Belief Engine & Semantic Analysis</div>
      </div>
    </div>

    <div class="header-actions">
      <!-- Strategy Selector -->
      <div style="display: flex; align-items: center; gap: 0.5rem;">
        <span style="font-size: 0.8rem; color: var(--text-muted); font-weight: 500;">Strategy:</span>
        <select
          class="select"
          style="padding: 0.35rem 0.75rem; font-size: 0.8rem; width: auto;"
          value={stats.active_strategy}
          onchange={(e) => handleStrategyChange(e.currentTarget.value)}
        >
          {#each stats.available_strategies as strat}
            <option value={strat}>{strat.toUpperCase()}</option>
          {/each}
        </select>
      </div>

      <!-- Theme Switcher -->
      <button class="btn-icon" onclick={toggleTheme} title="Toggle theme">
        {#if theme === 'dark'}
          <Sun size={18} />
        {:else}
          <Moon size={18} />
        {/if}
      </button>

      <!-- Clear Database -->
      <button class="btn-icon" onclick={() => (showResetModal = true)} title="Clear Database">
        <Trash2 size={18} color="var(--danger)" />
      </button>
    </div>
  </header>

  <!-- Executive Stats Cards -->
  <section class="stats-banner">
    <div class="stat-card">
      <div class="stat-icon-wrapper" style="background: var(--primary-light); color: var(--primary);">
        <FileText size={22} />
      </div>
      <div>
        <div class="stat-value">{stats.total_facts}</div>
        <div class="stat-label">Ingested Facts</div>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-icon-wrapper" style="background: var(--success-light); color: var(--success);">
        <ShieldCheck size={22} />
      </div>
      <div>
        <div class="stat-value">{stats.active_beliefs}</div>
        <div class="stat-label">Active Beliefs</div>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-icon-wrapper" style="background: var(--warning-light); color: var(--warning);">
        <AlertTriangle size={22} />
      </div>
      <div>
        <div class="stat-value">{stats.total_conflicts}</div>
        <div class="stat-label">Resolved Conflicts</div>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-icon-wrapper" style="background: var(--accent-cyan-light); color: var(--accent-cyan);">
        <Sparkles size={22} />
      </div>
      <div>
        <div class="stat-value" style="font-size: 1.15rem; text-transform: uppercase;">{stats.active_strategy}</div>
        <div class="stat-label">Active Engine Strategy</div>
      </div>
    </div>
  </section>

  <!-- Input & Processing Section -->
  <div class="workspace-grid">
    <!-- Left Column: Input Tabs -->
    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">
            <Layers size={18} color="var(--primary)" />
            Ingest Knowledge
          </div>
          <div class="card-description">Submit single statements or upload entire sequences</div>
        </div>

        <!-- Navigation Tabs -->
        <div class="tabs-nav">
          <button
            class="tab-btn"
            class:active={activeTab === 'single'}
            onclick={() => (activeTab = 'single')}
          >
            <Send size={15} /> Real-time Fact
          </button>
          <button
            class="tab-btn"
            class:active={activeTab === 'upload'}
            onclick={() => (activeTab = 'upload')}
          >
            <Upload size={15} /> Upload JSON
          </button>
        </div>
      </div>

      <!-- Tab 1: Single Fact Input -->
      {#if activeTab === 'single'}
        <div style="display: flex; flex-direction: column; gap: 1rem;">
          <div class="input-group">
            <span class="label">Statement / Fact Content</span>
            <textarea
              class="textarea"
              placeholder="Type an announcement, filing, or claim to evaluate (e.g. NovaTech Inc. reported Q4 revenue of $480M)..."
              bind:value={factContent}
            ></textarea>
          </div>

          <!-- Metadata row -->
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div class="input-group">
              <span class="label">Source Identification</span>
              <input class="input" type="text" bind:value={factSource} placeholder="e.g. SEC 10-K, PR Wire" />
            </div>

            <div class="input-group">
              <span class="label">Source Reliability</span>
              <select class="select" bind:value={factReliability}>
                <option value="high">High (Official Filings, Audited)</option>
                <option value="medium">Medium (News, Press Releases)</option>
                <option value="low">Low (Rumors, Unverified Leaks)</option>
              </select>
            </div>
          </div>

          <!-- Quick Presets -->
          <div>
            <span class="label" style="display: flex; align-items: center; gap: 0.35rem;">
              <Sparkles size={13} color="var(--primary)" /> Quick Benchmark Presets
            </span>
            <div class="presets-container">
              {#each presets as preset}
                <button class="preset-chip" onclick={() => applyPreset(preset)}>
                  {preset.label}
                </button>
              {/each}
            </div>
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
            <span style="font-size: 0.75rem; color: var(--text-muted);">
              Tip: Press <kbd style="background: var(--bg-surface-elevated); padding: 2px 6px; border-radius: 4px;">Ctrl+Enter</kbd> to submit
            </span>
            <button
              class="btn btn-primary"
              disabled={isSubmitting || !factContent.trim()}
              onclick={submitSingleFact}
            >
              {#if isSubmitting}
                <RefreshCw size={16} class="spinning" /> Analyzing...
              {:else}
                <Send size={16} /> Submit & Evaluate
              {/if}
            </button>
          </div>
        </div>

      <!-- Tab 2: File Upload -->
      {:else}
        <div style="display: flex; flex-direction: column; gap: 1.25rem;">
          <div
            class="dropzone"
            class:dragover={dragOver}
            role="button"
            tabindex="0"
            ondragover={(e) => { e.preventDefault(); dragOver = true; }}
            ondragleave={() => (dragOver = false)}
            ondrop={(e) => {
              e.preventDefault();
              dragOver = false;
              if (e.dataTransfer?.files?.[0]) {
                uploadFile = e.dataTransfer.files[0];
              }
            }}
            onclick={() => document.getElementById('json-file-input')?.click()}
            onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') document.getElementById('json-file-input')?.click(); }}
          >
            <div class="dropzone-icon">
              <Upload size={24} />
            </div>
            <div>
              <div style="font-weight: 600; font-size: 0.95rem;">
                {uploadFile ? uploadFile.name : 'Choose a JSON dataset file or drag here'}
              </div>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">
                Supports benchmark dataset format (e.g. data/jnaara_memory_facts_dataset.json)
              </div>
            </div>
            <input
              id="json-file-input"
              type="file"
              accept=".json"
              style="display: none;"
              onchange={(e) => {
                const target = e.currentTarget;
                if (target.files?.[0]) uploadFile = target.files[0];
              }}
            />
          </div>

          <div class="input-group">
            <span class="label">Benchmark Sequence Filter (Optional)</span>
            <select class="select" bind:value={uploadSequence}>
              <option value="">All Sequences (Process full dataset)</option>
              <option value="sequence_1_easy">Sequence 1 — Easy (Direct Contradictions, 27 facts)</option>
              <option value="sequence_2_medium">Sequence 2 — Medium (Partial & Cross-Entity, 27 facts)</option>
              <option value="sequence_3_hard">Sequence 3 — Hard (Nuanced Logical Inferences, 30 facts)</option>
            </select>
          </div>

          {#if uploadMessage}
            <div class="pill pill-primary" style="padding: 0.6rem 0.85rem; border-radius: var(--radius-md);">
              {uploadMessage}
            </div>
          {/if}

          <div style="display: flex; justify-content: flex-end;">
            <button
              class="btn btn-primary"
              disabled={!uploadFile || isUploading}
              onclick={handleFileUpload}
            >
              {#if isUploading}
                <RefreshCw size={16} class="spinning" /> Ingesting Dataset...
              {:else}
                <Upload size={16} /> Ingest File
              {/if}
            </button>
          </div>
        </div>
      {/if}
    </div>

    <!-- Right Column: Real-Time Engine Inspector -->
    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">
            <Sparkles size={18} color="var(--primary)" />
            Real-Time Processing Stream
          </div>
          <div class="card-description">Live claim extraction, contradiction detection & decisions</div>
        </div>
      </div>

      {#if liveResult}
        <div class="live-result-card">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span class="pill pill-neutral" style="font-family: var(--font-mono);">
              {liveResult.fact_id}
            </span>
            <span class="pill pill-success">
              <CheckCircle2 size={13} /> {liveResult.claims_count} Claim(s) Extracted
            </span>
          </div>

          <!-- Extracted Claims -->
          <div style="display: flex; flex-direction: column; gap: 0.5rem;">
            <span class="label">Extracted Claims</span>
            {#each liveResult.claims as claim}
              <div style="background: var(--bg-surface); padding: 0.65rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center;">
                <div>
                  <strong style="color: var(--text-primary);">{claim.entity}</strong>
                  <span style="color: var(--text-muted); font-size: 0.8rem;"> &bull; {claim.attribute}:</span>
                  <span style="color: var(--primary); font-family: var(--font-mono); font-weight: 600;"> {claim.value}</span>
                </div>
                <span class="pill pill-neutral" style="font-size: 0.7rem;">
                  Conf: {(claim.confidence * 100).toFixed(0)}%
                </span>
              </div>
            {/each}
          </div>

          <!-- Conflicts if any -->
          {#if liveResult.conflicts.length > 0}
            <div style="display: flex; flex-direction: column; gap: 0.5rem; margin-top: 0.5rem;">
              <span class="label" style="color: var(--warning);">
                <AlertTriangle size={13} /> Contradictions Detected ({liveResult.conflicts.length})
              </span>
              {#each liveResult.conflicts as conf}
                <div class="conflict-card">
                  <div style="font-size: 0.85rem; font-weight: 600;">{conf.description}</div>
                  {#if conf.resolution}
                    <div style="font-size: 0.8rem; color: var(--text-secondary); background: var(--bg-surface-subtle); padding: 0.45rem 0.65rem; border-radius: var(--radius-sm);">
                      <strong>Resolved via {conf.resolution.strategy_used}:</strong> {conf.resolution.rationale}
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}

          <!-- Decisions -->
          <div style="display: flex; flex-direction: column; gap: 0.4rem; margin-top: 0.5rem;">
            <span class="label">System Actions Taken</span>
            {#each liveResult.decisions as dec}
              <div style="font-size: 0.8rem; display: flex; align-items: center; gap: 0.5rem;">
                <span class="pill pill-primary" style="font-size: 0.68rem;">{dec.action}</span>
                <span style="color: var(--text-secondary);">{dec.reason}</span>
              </div>
            {/each}
          </div>
        </div>
      {:else}
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 260px; color: var(--text-muted); text-align: center; gap: 0.75rem;">
          <Sparkles size={36} color="var(--border-strong)" />
          <div>
            <div style="font-weight: 600; font-size: 0.95rem;">Awaiting incoming fact...</div>
            <div style="font-size: 0.8rem;">Type a statement on the left or select a preset to see the engine process it in real-time.</div>
          </div>
        </div>
      {/if}
    </div>
  </div>

  <!-- Knowledge Base Explorer -->
  <div class="card">
    <div class="card-header">
      <div style="display: flex; align-items: center; gap: 1.5rem;">
        <div class="card-title">
          <Database size={18} color="var(--primary)" />
          Knowledge Repository
        </div>

        <div class="tabs-nav" style="width: auto;">
          <button
            class="tab-btn"
            class:active={activeView === 'beliefs'}
            onclick={() => (activeView = 'beliefs')}
          >
            Active Beliefs ({beliefs.length})
          </button>
          <button
            class="tab-btn"
            class:active={activeView === 'conflicts'}
            onclick={() => (activeView = 'conflicts')}
          >
            Conflict Audit Log ({conflicts.length})
          </button>
        </div>
      </div>

      <div style="display: flex; align-items: center; gap: 0.75rem;">
        <div style="position: relative;">
          <input
            class="input"
            type="text"
            placeholder="Search by entity..."
            bind:value={searchQuery}
            oninput={() => { fetchBeliefs(); fetchConflicts(); }}
            style="padding-left: 2rem; width: 220px; font-size: 0.85rem;"
          />
          <Search size={15} style="position: absolute; left: 0.65rem; top: 50%; transform: translateY(-50%); color: var(--text-muted);" />
        </div>

        <button class="btn-icon" onclick={refreshAll} title="Refresh Knowledge">
          <RefreshCw size={16} />
        </button>
      </div>
    </div>

    <!-- Active Beliefs View -->
    {#if activeView === 'beliefs'}
      {#if beliefs.length === 0}
        <div style="text-align: center; padding: 3rem; color: var(--text-muted);">
          No active beliefs held. Ingest a fact or dataset to begin building the belief model.
        </div>
      {:else}
        <div class="beliefs-grid">
          {#each beliefs as b}
            <div class="belief-card">
              <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                  <div class="belief-entity">{b.entity}</div>
                  <div class="belief-attribute">{b.attribute}</div>
                </div>
                <span class="pill pill-neutral" style="font-size: 0.7rem;">v{b.version}</span>
              </div>

              <div class="belief-value">{b.value}</div>

              <div>
                <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.3rem;">
                  <span>Confidence</span>
                  <span>{(b.confidence * 100).toFixed(0)}%</span>
                </div>
                <div class="confidence-track">
                  <div class="confidence-fill" style="width: {b.confidence * 100}%;"></div>
                </div>
              </div>

              <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-subtle); padding-top: 0.75rem; margin-top: auto;">
                <span style="font-size: 0.75rem; color: var(--text-muted);">
                  {b.supporting_fact_ids.length} support &bull; {b.contradicting_fact_ids.length} conflict
                </span>

                <button
                  class="btn btn-secondary"
                  style="padding: 0.35rem 0.65rem; font-size: 0.75rem;"
                  onclick={() => openProvenance(b.id)}
                >
                  <History size={13} /> Provenance
                </button>
              </div>
            </div>
          {/each}
        </div>
      {/if}

    <!-- Conflicts View -->
    {:else}
      {#if conflicts.length === 0}
        <div style="text-align: center; padding: 3rem; color: var(--text-muted);">
          No contradictions recorded. When conflicting claims appear, their audit log and resolution details will appear here.
        </div>
      {:else}
        <div style="display: flex; flex-direction: column; gap: 0.75rem;">
          {#each conflicts as c}
            <div class="conflict-card" class:high-severity={c.severity === 'high'}>
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                  <strong style="color: var(--text-primary);">{c.entity}</strong>
                  <span style="font-size: 0.8rem; color: var(--text-muted);">&bull; {c.attribute}</span>
                  <span class="pill pill-warning" style="font-size: 0.68rem;">{c.conflict_type.toUpperCase()}</span>
                </div>
                <span style="font-size: 0.75rem; color: var(--text-muted);">
                  {new Date(c.detected_at).toLocaleTimeString()}
                </span>
              </div>

              <div style="font-size: 0.88rem;">{c.description}</div>

              {#if c.resolution}
                <div style="background: var(--bg-surface-subtle); padding: 0.65rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); display: flex; flex-direction: column; gap: 0.25rem;">
                  <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <span class="pill pill-success" style="font-size: 0.68rem;">
                      WINNER: {c.resolution.winner.replace('_', ' ').toUpperCase()}
                    </span>
                    <span style="font-size: 0.78rem; color: var(--text-muted);">
                      Strategy: {c.resolution.strategy_used}
                    </span>
                  </div>
                  <div style="font-size: 0.82rem; color: var(--text-secondary);">
                    {c.resolution.rationale}
                  </div>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    {/if}
  </div>
</div>

<!-- Provenance Audit Modal -->
{#if activeProvenance}
  <div
    class="modal-backdrop"
    role="presentation"
    onclick={() => (activeProvenance = null)}
    onkeydown={(e) => { if (e.key === 'Escape') activeProvenance = null; }}
  >
    <div
      class="modal-dialog"
      role="dialog"
      aria-modal="true"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <div class="modal-header">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <History size={20} color="var(--primary)" />
          <div>
            <div style="font-weight: 700; font-size: 1.05rem;">
              Provenance Audit Trail
            </div>
            <div style="font-size: 0.78rem; color: var(--text-muted);">
              Belief ID: {activeProvenance.belief.id}
            </div>
          </div>
        </div>
        <button class="btn-icon" onclick={() => (activeProvenance = null)}>
          <X size={18} />
        </button>
      </div>

      <div class="modal-body">
        <!-- Current State Summary -->
        <div style="background: var(--bg-surface-elevated); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center;">
          <div>
            <div style="font-size: 0.8rem; color: var(--text-muted);">CURRENT STATE (v{activeProvenance.belief.version})</div>
            <div style="font-size: 1.15rem; font-weight: 700; color: var(--text-primary); margin-top: 0.2rem;">
              {activeProvenance.belief.entity} &bull; {activeProvenance.belief.attribute}
            </div>
          </div>
          <div class="belief-value" style="font-size: 1.1rem;">
            {activeProvenance.belief.value}
          </div>
        </div>

        <!-- History Timeline -->
        <div style="margin-top: 0.5rem;">
          <div class="label" style="margin-bottom: 0.85rem;">Version Mutation History</div>
          <div class="timeline">
            {#each activeProvenance.history as h}
              <div class="timeline-node">
                <div class="timeline-dot"></div>
                <div style="background: var(--bg-surface-subtle); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 0.75rem 1rem;">
                  <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.35rem;">
                    <strong>Version {h.version}</strong>
                    <span>Fact: {h.changed_by_fact_id}</span>
                  </div>
                  <div style="font-size: 0.9rem; font-family: var(--font-mono); color: var(--primary);">
                    {#if h.old_value}
                      <span style="color: var(--text-muted); text-decoration: line-through;">{h.old_value}</span> &rarr;
                    {/if}
                    {h.new_value}
                  </div>
                  {#if h.reason}
                    <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.35rem;">
                      {h.reason}
                    </div>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        </div>

        <!-- Supporting Facts -->
        {#if activeProvenance.supporting_facts.length > 0}
          <div>
            <div class="label" style="margin-bottom: 0.5rem;">Supporting Evidence Facts</div>
            <div style="display: flex; flex-direction: column; gap: 0.4rem;">
              {#each activeProvenance.supporting_facts as fact}
                <div style="font-size: 0.82rem; background: var(--bg-surface-subtle); padding: 0.55rem 0.8rem; border-radius: var(--radius-sm); border-left: 3px solid var(--success);">
                  <div style="color: var(--text-muted); font-size: 0.72rem; margin-bottom: 0.15rem;">
                    {fact.source} &bull; {fact.id}
                  </div>
                  "{fact.content}"
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<!-- Reset Confirmation Dialog -->
{#if showResetModal}
  <div
    class="modal-backdrop"
    role="presentation"
    onclick={() => (showResetModal = false)}
    onkeydown={(e) => { if (e.key === 'Escape') showResetModal = false; }}
  >
    <div
      class="modal-dialog"
      style="max-width: 440px;"
      role="dialog"
      aria-modal="true"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <div class="modal-header">
        <div style="display: flex; align-items: center; gap: 0.5rem; color: var(--danger);">
          <AlertTriangle size={20} />
          <div style="font-weight: 700;">Reset Belief Database</div>
        </div>
        <button class="btn-icon" onclick={() => (showResetModal = false)}>
          <X size={18} />
        </button>
      </div>
      <div class="modal-body">
        <p style="font-size: 0.9rem; color: var(--text-secondary);">
          Are you sure you want to clear all facts, active beliefs, contradictions, and provenance history? This cannot be undone.
        </p>
        <div style="display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.5rem;">
          <button class="btn btn-secondary" onclick={() => (showResetModal = false)}>Cancel</button>
          <button class="btn btn-danger-subtle" onclick={executeReset}>Clear Everything</button>
        </div>
      </div>
    </div>
  </div>
{/if}

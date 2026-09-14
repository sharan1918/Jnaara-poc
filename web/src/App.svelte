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
    ChevronLeft,
    X,
    Clock,
    ArrowUpDown,
    Table,
    LayoutGrid,
    Play,
    Pause,
    SkipBack,
    SkipForward,
    GitCommit,
    SlidersHorizontal
  } from 'lucide-svelte';

  // Types
  interface TimelineFact {
    id: string;
    timestamp: string;
    source: string;
    source_reliability: string;
    content: string;
  }

  interface TimelineBeliefSnapshot {
    id: string;
    entity: string;
    attribute: string;
    value: string;
    confidence: number;
    version: number;
    is_updated_in_this_step: boolean;
    status: string;
  }

  interface TimelineStep {
    step_number: number;
    fact: TimelineFact;
    claims: Array<{
      id: string;
      entity: string;
      attribute: string;
      value: string;
      claim_type: string;
      confidence: number;
    }>;
    decisions: Array<{
      id: string;
      action: string;
      reason: string;
      tier: string;
    }>;
    conflicts: Array<{
      id: string;
      entity: string;
      attribute: string;
      conflict_type: string;
      description: string;
      resolution?: {
        winner: string;
        strategy_used: string;
        rationale: string;
      };
    }>;
    mutations: Array<{
      version: number;
      old_value: string | null;
      new_value: string;
      old_confidence: number | null;
      new_confidence: number;
      changed_by_fact_id: string;
      reason: string | null;
    }>;
    action_summary: string;
    has_conflict: boolean;
    beliefs_snapshot: TimelineBeliefSnapshot[];
  }

  interface Belief {
    id: string;
    entity: string;
    attribute: string;
    value: string;
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
  let activeView = $state<'timeline' | 'beliefs' | 'conflicts'>('timeline');

  // Timeline State & Playback
  let timelineSteps = $state<TimelineStep[]>([]);
  let currentStepIndex = $state(0);
  let isPlayingTimeline = $state(false);
  let playIntervalTimer: any = null;
  let timelineMode = $state<'stepper' | 'stream'>('stepper');
  let currentStep = $derived(timelineSteps[currentStepIndex] || null);

  function goToStep(index: number) {
    if (timelineSteps.length === 0) return;
    currentStepIndex = Math.max(0, Math.min(index, timelineSteps.length - 1));
  }

  function nextStep() {
    if (currentStepIndex < timelineSteps.length - 1) {
      currentStepIndex++;
    } else if (isPlayingTimeline) {
      pauseTimeline();
    }
  }

  function prevStep() {
    if (currentStepIndex > 0) {
      currentStepIndex--;
    }
  }

  function togglePlayTimeline() {
    if (isPlayingTimeline) {
      pauseTimeline();
    } else {
      playTimeline();
    }
  }

  function playTimeline() {
    if (timelineSteps.length === 0) return;
    if (currentStepIndex >= timelineSteps.length - 1) {
      currentStepIndex = 0;
    }
    isPlayingTimeline = true;
    playIntervalTimer = setInterval(() => {
      if (currentStepIndex < timelineSteps.length - 1) {
        currentStepIndex++;
      } else {
        pauseTimeline();
      }
    }, 2000);
  }

  function pauseTimeline() {
    isPlayingTimeline = false;
    if (playIntervalTimer) {
      clearInterval(playIntervalTimer);
      playIntervalTimer = null;
    }
  }

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
  let selectedEntityFilter = $state<string>('all');
  let selectedFactFilter = $state<string>('all');
  let sortBy = $state<'sequence' | 'entity' | 'conflicts' | 'confidence'>('sequence');
  let repositoryDisplayMode = $state<'dossier' | 'grid' | 'table'>('dossier');

  // Fact Sequence Helper
  function parseFactNum(id: string): number {
    const match = id.match(/\d+/);
    return match ? parseInt(match[0], 10) : 9999;
  }

  function getFactSequenceInfo(b: Belief) {
    const allFacts = [
      ...(b.contradicting_fact_ids || []),
      ...(b.supporting_fact_ids || [])
    ].filter(Boolean);

    if (allFacts.length === 0) {
      return {
        originFactId: 'E?',
        latestFactId: 'E?',
        sequenceNum: 9999,
        allFactIds: [] as string[],
        hasEvolution: false
      };
    }

    const sorted = [...new Set(allFacts)].sort((a, b) => parseFactNum(a) - parseFactNum(b));
    const originFactId = sorted[0];
    const latestFactId = (b.supporting_fact_ids && b.supporting_fact_ids.length > 0)
      ? b.supporting_fact_ids[b.supporting_fact_ids.length - 1]
      : sorted[sorted.length - 1];
    const sequenceNum = parseFactNum(originFactId);
    const hasEvolution = sorted.length > 1 || b.version > 1;

    return {
      originFactId,
      latestFactId,
      sequenceNum,
      allFactIds: sorted,
      hasEvolution
    };
  }

  // Available Unique Facts in Sequence
  let availableFactSequence = $derived.by(() => {
    const factMap = new Map<string, { id: string; num: number; hasConflicts: boolean; count: number }>();
    for (const b of beliefs) {
      const info = getFactSequenceInfo(b);
      for (const fid of info.allFactIds) {
        const existing = factMap.get(fid) || {
          id: fid,
          num: parseFactNum(fid),
          hasConflicts: false,
          count: 0
        };
        existing.count++;
        if (b.contradicting_fact_ids.includes(fid) || b.version > 1) {
          existing.hasConflicts = true;
        }
        factMap.set(fid, existing);
      }
    }
    return Array.from(factMap.values()).sort((a, b) => a.num - b.num);
  });

  // Derived Entity Breakdown
  let entityList = $derived.by(() => {
    const map = new Map<string, { total: number; conflicts: number }>();
    for (const b of beliefs) {
      const entry = map.get(b.entity) || { total: 0, conflicts: 0 };
      entry.total++;
      if (b.contradicting_fact_ids.length > 0 || b.version > 1) {
        entry.conflicts++;
      }
      map.set(b.entity, entry);
    }
    return Array.from(map.entries())
      .map(([name, stat]) => ({ name, ...stat }))
      .sort((a, b) => b.total - a.total);
  });

  // Filtered & Sorted Beliefs
  let visibleBeliefs = $derived.by(() => {
    let list = beliefs;
    if (selectedEntityFilter !== 'all') {
      list = list.filter((b) => b.entity.toLowerCase() === selectedEntityFilter.toLowerCase());
    }
    if (selectedFactFilter !== 'all') {
      list = list.filter((b) => {
        const info = getFactSequenceInfo(b);
        return info.allFactIds.includes(selectedFactFilter);
      });
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((b) => {
        const info = getFactSequenceInfo(b);
        return (
          b.entity.toLowerCase().includes(q) ||
          b.attribute.toLowerCase().includes(q) ||
          b.value.toLowerCase().includes(q) ||
          info.originFactId.toLowerCase().includes(q) ||
          info.allFactIds.some((f) => f.toLowerCase().includes(q))
        );
      });
    }

    const sortedList = [...list];
    sortedList.sort((a, b) => {
      if (sortBy === 'sequence') {
        const sa = getFactSequenceInfo(a).sequenceNum;
        const sb = getFactSequenceInfo(b).sequenceNum;
        if (sa !== sb) return sa - sb;
        return a.entity.localeCompare(b.entity);
      }
      if (sortBy === 'entity') {
        return a.entity.localeCompare(b.entity) || a.attribute.localeCompare(b.attribute);
      }
      if (sortBy === 'conflicts') {
        const aConf = (a.contradicting_fact_ids.length > 0 || a.version > 1) ? 1 : 0;
        const bConf = (b.contradicting_fact_ids.length > 0 || b.version > 1) ? 1 : 0;
        return bConf - aConf || b.version - a.version;
      }
      if (sortBy === 'confidence') {
        return b.confidence - a.confidence;
      }
      return 0;
    });

    return sortedList;
  });

  // Grouped Beliefs for Entity Dossier view
  let groupedByEntity = $derived.by(() => {
    const map = new Map<string, Belief[]>();
    for (const b of visibleBeliefs) {
      if (!map.has(b.entity)) {
        map.set(b.entity, []);
      }
      map.get(b.entity)!.push(b);
    }
    const groups = Array.from(map.entries()).map(([entity, items]) => {
      // Sort items inside dossier by sequence number
      items.sort((a, b) => {
        const sa = getFactSequenceInfo(a).sequenceNum;
        const sb = getFactSequenceInfo(b).sequenceNum;
        return sa - sb;
      });
      const earliestSeq = items.length > 0 ? getFactSequenceInfo(items[0]).sequenceNum : 9999;
      return {
        entity,
        items,
        earliestSeq,
        conflictsCount: items.filter((i) => i.contradicting_fact_ids.length > 0 || i.version > 1).length
      };
    });

    if (sortBy === 'sequence') {
      groups.sort((a, b) => a.earliestSeq - b.earliestSeq);
    }
    return groups;
  });

  // Top Contradiction Highlights
  let topHighlights = $derived.by(() => {
    return conflicts.slice(0, 3).map((c) => {
      const match = beliefs.find(
        (b) => b.entity.toLowerCase() === c.entity.toLowerCase() && b.attribute.toLowerCase() === c.attribute.toLowerCase()
      );
      let winnerLabel = 'Incoming Claim Accepted';
      if (c.resolution?.winner === 'existing_belief') {
        winnerLabel = 'Existing Ground Truth Retained';
      } else if (c.resolution?.winner === 'both_retained') {
        winnerLabel = 'Both Contextualized';
      }
      return {
        entity: c.entity,
        attribute: c.attribute,
        description: c.description,
        winner: c.resolution?.winner,
        winnerLabel,
        establishedValue: match ? match.value : null,
        strategy: c.resolution?.strategy_used || 'source_credibility',
        rationale: c.resolution?.rationale
      };
    });
  });

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

  async function fetchTimeline() {
    try {
      const res = await fetch('/api/timeline');
      if (res.ok) {
        const data = await res.json();
        timelineSteps = data.steps;
        if (timelineSteps.length > 0 && currentStepIndex >= timelineSteps.length) {
          currentStepIndex = timelineSteps.length - 1;
        }
      }
    } catch (err) {
      console.error('Failed to fetch timeline:', err);
    }
  }

  async function refreshAll() {
    await Promise.all([fetchStats(), fetchBeliefs(), fetchConflicts(), fetchTimeline()]);
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
        const savedNotice = data.output_file ? ` (Saved to: ${data.output_file})` : '';
        uploadMessage = `Successfully processed ${data.total_processed} facts (${data.total_claims} claims, ${data.total_conflicts} conflicts detected).${savedNotice}`;
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
                <RefreshCw size={16} class="spinning" /> Evaluating Dataset...
              {:else}
                <Upload size={16} /> Ingest & Evaluate
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

          {#if liveResult.output_file}
            <div style="font-size: 0.75rem; color: var(--primary); font-family: var(--font-mono); word-break: break-all; background: var(--bg-surface); padding: 0.4rem 0.6rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
              📁 Saved to: {liveResult.output_file}
            </div>
          {/if}

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
      <div style="display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;">
        <div class="card-title">
          <Database size={18} color="var(--primary)" />
          Knowledge Repository
        </div>

        <div class="tabs-nav" style="width: auto;">
          <button
            class="tab-btn"
            class:active={activeView === 'timeline'}
            onclick={() => (activeView = 'timeline')}
          >
            <Clock size={13} /> Step-by-Step Evolution ({timelineSteps.length})
          </button>
          <button
            class="tab-btn"
            class:active={activeView === 'beliefs'}
            onclick={() => (activeView = 'beliefs')}
          >
            <Layers size={13} /> Active Beliefs ({beliefs.length})
          </button>
          <button
            class="tab-btn"
            class:active={activeView === 'conflicts'}
            onclick={() => (activeView = 'conflicts')}
          >
            <ShieldCheck size={13} /> Conflict Audit Log ({conflicts.length})
          </button>
        </div>

        {#if activeView === 'beliefs'}
          <div class="view-mode-toggle">
            <button
              class="view-mode-btn"
              class:active={repositoryDisplayMode === 'dossier'}
              onclick={() => (repositoryDisplayMode = 'dossier')}
              title="Group beliefs by company / entity cards"
            >
              <Layers size={13} /> Dossier View
            </button>
            <button
              class="view-mode-btn"
              class:active={repositoryDisplayMode === 'table'}
              onclick={() => (repositoryDisplayMode = 'table')}
              title="Spreadsheet Table View"
            >
              <Table size={13} /> Table
            </button>
            <button
              class="view-mode-btn"
              class:active={repositoryDisplayMode === 'grid'}
              onclick={() => (repositoryDisplayMode = 'grid')}
              title="Flat Card Grid"
            >
              <LayoutGrid size={13} /> Flat Grid
            </button>
          </div>

          <div style="display: flex; align-items: center; gap: 0.35rem; background: var(--bg-surface-elevated); padding: 0.2rem 0.5rem; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
            <ArrowUpDown size={13} color="var(--text-muted)" />
            <span style="font-size: 0.72rem; font-weight: 600; color: var(--text-muted);">Sort:</span>
            <select
              bind:value={sortBy}
              style="background: transparent; border: none; color: var(--text-primary); font-size: 0.74rem; font-weight: 600; cursor: pointer; outline: none;"
            >
              <option value="sequence">Sequence (E1 → E27)</option>
              <option value="entity">Entity (A-Z)</option>
              <option value="conflicts">Most Contradicted</option>
              <option value="confidence">Highest Confidence</option>
            </select>
          </div>
        {/if}
      </div>

      <div style="display: flex; align-items: center; gap: 0.75rem;">
        <div style="position: relative;">
          <input
            class="input"
            type="text"
            placeholder="Search attribute or entity..."
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

    <!-- View 1: Step-by-Step Evolution Timeline Replay -->
    {#if activeView === 'timeline'}
      {#if timelineSteps.length === 0}
        <div style="text-align: center; padding: 3rem; color: var(--text-muted); display: flex; flex-direction: column; align-items: center; gap: 0.75rem;">
          <Clock size={36} color="var(--border-strong)" />
          <div>
            <div style="font-weight: 600; font-size: 0.95rem;">No sequential facts recorded yet</div>
            <div style="font-size: 0.8rem; margin-top: 0.25rem;">Submit facts on the left or upload a sequence dataset to watch the belief engine evolve step-by-step.</div>
          </div>
        </div>
      {:else}
        <div class="timeline-player-card">
          <!-- Playback Controls Bar -->
          <div class="timeline-player-bar">
            <div class="timeline-controls">
              <button
                class="btn-icon"
                onclick={() => goToStep(0)}
                disabled={currentStepIndex === 0}
                title="Jump to First Step"
              >
                <SkipBack size={15} />
              </button>
              <button
                class="btn-icon"
                onclick={prevStep}
                disabled={currentStepIndex === 0}
                title="Previous Fact"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                class="btn btn-primary"
                style="padding: 0.35rem 0.85rem; font-size: 0.8rem; display: inline-flex; align-items: center; gap: 0.4rem;"
                onclick={togglePlayTimeline}
                title={isPlayingTimeline ? "Pause Auto-Playback" : "Auto-Play Step by Step"}
              >
                {#if isPlayingTimeline}
                  <Pause size={13} /> Pause Replay
                {:else}
                  <Play size={13} /> Play Step-by-Step
                {/if}
              </button>
              <button
                class="btn-icon"
                onclick={nextStep}
                disabled={currentStepIndex >= timelineSteps.length - 1}
                title="Next Fact"
              >
                <ChevronRight size={16} />
              </button>
              <button
                class="btn-icon"
                onclick={() => goToStep(timelineSteps.length - 1)}
                disabled={currentStepIndex >= timelineSteps.length - 1}
                title="Jump to Latest Step"
              >
                <SkipForward size={15} />
              </button>
            </div>

            <div style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
              <div style="font-size: 0.85rem; font-weight: 700; color: var(--text-primary); display: flex; align-items: center; gap: 0.4rem;">
                <span class="pill pill-primary" style="font-size: 0.72rem;">Step {currentStepIndex + 1} of {timelineSteps.length}</span>
                <span>Fact {currentStep?.fact.id}</span>
                {#if currentStep?.has_conflict}
                  <span class="pill pill-warning" style="font-size: 0.68rem;">⚡ Contradiction Step</span>
                {/if}
              </div>

              <!-- Stepper vs Stream Toggle -->
              <div class="view-mode-toggle">
                <button
                  class="view-mode-btn"
                  class:active={timelineMode === 'stepper'}
                  onclick={() => (timelineMode = 'stepper')}
                  title="Interactive Step Player"
                >
                  <SlidersHorizontal size={13} /> Step Player
                </button>
                <button
                  class="view-mode-btn"
                  class:active={timelineMode === 'stream'}
                  onclick={() => (timelineMode = 'stream')}
                  title="Full Continuous Story Stream"
                >
                  <FileText size={13} /> Full Stream
                </button>
              </div>
            </div>
          </div>

          <!-- Step Scrubber Ribbon -->
          <div class="timeline-scrubber">
            {#each timelineSteps as s, sIdx}
              <button
                class="timeline-step-pill"
                class:active={sIdx === currentStepIndex}
                class:has-conflict={s.has_conflict}
                onclick={() => goToStep(sIdx)}
                title="Step {s.step_number}: Fact {s.fact.id} ({s.action_summary})"
              >
                <span>#{s.step_number}</span>
                <span>{s.fact.id}</span>
                {#if s.has_conflict}
                  <span style="color: var(--warning); font-size: 0.65rem;">⚡</span>
                {/if}
              </button>
            {/each}
          </div>

          <!-- Mode 1: Interactive Stepper (Split View) -->
          {#if timelineMode === 'stepper' && currentStep}
            <div class="timeline-split-view">
              <!-- Left: Fact Ingestion & Engine Action -->
              <div class="timeline-fact-box">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.4rem;">
                  <div style="display: flex; align-items: center; gap: 0.45rem;">
                    <span class="seq-num-badge" style="font-size: 0.75rem;">Step #{currentStep.step_number}</span>
                    <strong style="font-size: 0.9rem; color: var(--text-primary);">Incoming Fact: {currentStep.fact.id}</strong>
                  </div>
                  <div style="display: flex; align-items: center; gap: 0.35rem;">
                    <span class="pill pill-neutral" style="font-size: 0.7rem;">{currentStep.fact.source}</span>
                    <span class="pill pill-{currentStep.fact.source_reliability === 'high' ? 'success' : currentStep.fact.source_reliability === 'low' ? 'danger' : 'warning'}" style="font-size: 0.65rem;">
                      {currentStep.fact.source_reliability.toUpperCase()}
                    </span>
                  </div>
                </div>

                <div class="timeline-quote">
                  "{currentStep.fact.content}"
                </div>

                <!-- Claims Extracted -->
                {#if currentStep.claims.length > 0}
                  <div style="display: flex; flex-direction: column; gap: 0.35rem;">
                    <span style="font-size: 0.74rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">
                      Extracted Claims ({currentStep.claims.length})
                    </span>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.4rem;">
                      {#each currentStep.claims as clm}
                        <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); padding: 0.3rem 0.55rem; border-radius: var(--radius-sm); font-size: 0.76rem; display: flex; align-items: center; gap: 0.35rem;">
                          <strong style="color: var(--text-primary);">{clm.entity} &bull; {clm.attribute}:</strong>
                          <span style="color: var(--primary); font-family: monospace;">{clm.value}</span>
                          <span style="opacity: 0.7; font-size: 0.7rem;">({(clm.confidence * 100).toFixed(0)}%)</span>
                        </div>
                      {/each}
                    </div>
                  </div>
                {/if}

                <!-- Impact / Action Taken -->
                <div style="display: flex; flex-direction: column; gap: 0.35rem; margin-top: 0.25rem;">
                  <span style="font-size: 0.74rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">
                    Engine Decision & Resolution
                  </span>
                  {#if currentStep.has_conflict && currentStep.conflicts.length > 0}
                    {@const c = currentStep.conflicts[0]}
                    <div class="timeline-action-card conflict">
                      <div style="font-weight: 700; color: var(--warning); display: flex; align-items: center; gap: 0.4rem;">
                        <AlertTriangle size={14} /> Contradiction Detected & Resolved!
                      </div>
                      <div style="font-size: 0.8rem; color: var(--text-secondary); line-height: 1.35;">
                        {c.description}
                      </div>
                      {#if c.resolution}
                        <div style="background: var(--bg-surface); padding: 0.45rem 0.65rem; border-radius: var(--radius-sm); font-size: 0.76rem; border: 1px solid rgba(245, 158, 11, 0.3); margin-top: 0.2rem;">
                          <div>
                            <strong>Decision:</strong> Winner is <span class="pill pill-success" style="font-size: 0.65rem;">{c.resolution.winner.replace('_', ' ').toUpperCase()}</span> via <em>{c.resolution.strategy_used.replace('_', ' ')}</em>
                          </div>
                          {#if c.resolution.rationale}
                            <div style="color: var(--text-secondary); font-size: 0.74rem; margin-top: 0.2rem;">
                              {c.resolution.rationale}
                            </div>
                          {/if}
                        </div>
                      {/if}
                    </div>
                  {:else if currentStep.mutations.length > 0}
                    {@const m = currentStep.mutations[0]}
                    <div class="timeline-action-card create">
                      <div style="font-weight: 700; color: var(--success); display: flex; align-items: center; gap: 0.4rem;">
                        <CheckCircle2 size={14} />
                        {#if m.old_value}
                          Ground Truth Updated: {m.old_value} → {m.new_value}
                        {:else}
                          Initial Belief Established: {m.new_value}
                        {/if}
                      </div>
                      {#if m.reason}
                        <div style="font-size: 0.78rem; color: var(--text-secondary);">
                          {m.reason}
                        </div>
                      {/if}
                    </div>
                  {:else if currentStep.decisions.length > 0}
                    <div class="timeline-action-card neutral">
                      <div style="font-size: 0.8rem; display: flex; align-items: center; gap: 0.4rem;">
                        <span class="pill pill-primary" style="font-size: 0.65rem;">{currentStep.decisions[0].action}</span>
                        <span style="color: var(--text-secondary);">{currentStep.decisions[0].reason}</span>
                      </div>
                    </div>
                  {:else}
                    <div class="timeline-action-card neutral" style="font-size: 0.8rem; color: var(--text-muted);">
                      Fact ingested into context memory.
                    </div>
                  {/if}
                </div>
              </div>

              <!-- Right: Evolving Beliefs Snapshot -->
              <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <div>
                    <div style="font-weight: 700; font-size: 0.95rem; color: var(--text-primary); display: flex; align-items: center; gap: 0.45rem;">
                      <Database size={16} color="var(--primary)" />
                      <span>Belief State at Step #{currentStep.step_number}</span>
                    </div>
                    <div style="font-size: 0.75rem; color: var(--text-muted);">
                      {currentStep.beliefs_snapshot.length} active belief{currentStep.beliefs_snapshot.length > 1 ? 's' : ''} held after this step
                    </div>
                  </div>
                </div>

                {#if currentStep.beliefs_snapshot.length === 0}
                  <div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.85rem; background: var(--bg-surface-subtle); border-radius: var(--radius-md);">
                    No beliefs formed yet at this step.
                  </div>
                {:else}
                  <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0.75rem; max-height: 480px; overflow-y: auto; padding-right: 0.25rem;">
                    {#each currentStep.beliefs_snapshot as b}
                      <div
                        class="timeline-belief-card"
                        class:step-updated={b.is_updated_in_this_step && !currentStep.has_conflict}
                        class:step-conflict-updated={b.is_updated_in_this_step && currentStep.has_conflict}
                      >
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                          <span style="font-size: 0.72rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">
                            {b.attribute}
                          </span>
                          {#if b.is_updated_in_this_step}
                            <span class="pill pill-{currentStep.has_conflict ? 'warning' : 'success'}" style="font-size: 0.65rem; font-weight: 700;">
                              ⚡ Updated Now
                            </span>
                          {:else}
                            <span class="pill pill-neutral" style="font-size: 0.65rem;">v{b.version}</span>
                          {/if}
                        </div>

                        <div style="font-size: 0.78rem; font-weight: 600; color: var(--text-secondary);">
                          {b.entity}
                        </div>

                        <div style="font-size: 0.95rem; font-weight: 700; color: var(--text-primary); line-height: 1.35;">
                          {b.value}
                        </div>

                        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: auto; padding-top: 0.35rem; border-top: 1px solid var(--border-subtle); font-size: 0.72rem; color: var(--text-muted);">
                          <span>Confidence: {(b.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            </div>

          <!-- Mode 2: Full Continuous Narrative Stream -->
          {:else if timelineMode === 'stream'}
            <div class="timeline-stream-container" style="margin-top: 0.5rem;">
              {#each timelineSteps as s}
                <div class="timeline-stream-item" class:has-conflict={s.has_conflict}>
                  <div class="timeline-stream-dot">#{s.step_number}</div>

                  <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
                    <div style="display: flex; align-items: center; gap: 0.45rem;">
                      <strong style="color: var(--text-primary); font-size: 0.9rem;">Step {s.step_number}: Fact {s.fact.id}</strong>
                      <span class="pill pill-neutral" style="font-size: 0.7rem;">{s.fact.source}</span>
                      <span class="pill pill-{s.fact.source_reliability === 'high' ? 'success' : s.fact.source_reliability === 'low' ? 'danger' : 'warning'}" style="font-size: 0.65rem;">
                        {s.fact.source_reliability.toUpperCase()}
                      </span>
                    </div>
                    {#if s.has_conflict}
                      <span class="pill pill-warning" style="font-size: 0.7rem;">⚡ Contradiction Resolved</span>
                    {/if}
                  </div>

                  <div style="font-style: italic; color: var(--text-secondary); font-size: 0.88rem; line-height: 1.4; background: var(--bg-surface-subtle); padding: 0.65rem 0.85rem; border-radius: var(--radius-sm);">
                    "{s.fact.content}"
                  </div>

                  <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; border-top: 1px solid var(--border-subtle); padding-top: 0.5rem; font-size: 0.8rem;">
                    <div>
                      <strong style="color: var(--text-primary);">{s.action_summary}</strong>
                    </div>
                    <div style="color: var(--text-muted); font-size: 0.75rem;">
                      {s.beliefs_snapshot.length} active belief{s.beliefs_snapshot.length > 1 ? 's' : ''} held after this step
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/if}

    <!-- Active Beliefs View -->
    {:else if activeView === 'beliefs'}
      {#if beliefs.length === 0}
        <div style="text-align: center; padding: 3rem; color: var(--text-muted);">
          No active beliefs held. Ingest a fact or dataset to begin building the belief model.
        </div>
      {:else}
        <!-- Executive Contradiction Highlights (What Changed) -->
        {#if topHighlights.length > 0}
          <div class="highlights-card">
            <div class="highlights-title">
              <Sparkles size={16} color="var(--primary)" />
              <span>Key Contradictions Resolved by Engine</span>
            </div>
            <div class="highlights-grid">
              {#each topHighlights as h}
                <div class="highlight-item">
                  <div style="font-weight: 700; color: var(--text-primary); display: flex; align-items: center; justify-content: space-between;">
                    <span>{h.entity} &bull; {h.attribute}</span>
                    <span class="pill pill-warning" style="font-size: 0.65rem;">Resolved</span>
                  </div>
                  <div style="color: var(--text-secondary); font-size: 0.78rem; line-height: 1.35; margin-top: 0.15rem;">
                    {h.description}
                  </div>
                  <div class="highlight-decision-box">
                    {#if h.establishedValue}
                      <div style="font-weight: 700; color: var(--success); display: flex; align-items: center; gap: 0.35rem;">
                        <CheckCircle2 size={13} /> Ground Truth: {h.establishedValue}
                      </div>
                    {/if}
                    <div style="color: var(--text-secondary); font-size: 0.74rem;">
                      Decision: <strong>{h.winnerLabel}</strong> ({h.strategy.replace('_', ' ')})
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Entity Filter Chips -->
        {#if entityList.length > 1}
          <div class="entity-filter-bar">
            <span style="font-size: 0.78rem; font-weight: 600; color: var(--text-muted); margin-right: 0.25rem;">Filter Entity:</span>
            <button
              class="entity-chip"
              class:active={selectedEntityFilter === 'all'}
              onclick={() => (selectedEntityFilter = 'all')}
            >
              All Entities ({beliefs.length})
            </button>
            {#each entityList as ent}
              <button
                class="entity-chip"
                class:active={selectedEntityFilter.toLowerCase() === ent.name.toLowerCase()}
                onclick={() => (selectedEntityFilter = ent.name)}
              >
                <span>{ent.name}</span>
                <span style="opacity: 0.7; font-size: 0.75rem;">({ent.total})</span>
                {#if ent.conflicts > 0}
                  <span style="color: var(--warning); font-size: 0.7rem; font-weight: 700;">⚡{ent.conflicts}</span>
                {/if}
              </button>
            {/each}
          </div>
        {/if}

        <!-- Mode 1: Entity Dossiers View (Default Cards) -->
        {#if repositoryDisplayMode === 'dossier'}
          <div style="display: flex; flex-direction: column; gap: 1.25rem; margin-top: 0.5rem;">
            {#each groupedByEntity as group}
              <div class="entity-dossier-card">
                <div class="entity-dossier-header">
                  <div class="entity-dossier-title">
                    <Layers size={18} color="var(--primary)" />
                    <span>{group.entity}</span>
                    <span class="pill pill-neutral" style="font-size: 0.72rem;">{group.items.length} Tracked Attribute{group.items.length > 1 ? 's' : ''}</span>
                    {#if group.conflictsCount > 0}
                      <span class="pill pill-warning" style="font-size: 0.72rem;">
                        <AlertTriangle size={12} /> {group.conflictsCount} Contradiction{group.conflictsCount > 1 ? 's' : ''} Resolved
                      </span>
                    {/if}
                  </div>
                </div>

                <div class="dossier-grid">
                  {#each group.items as b}
                    {@const info = getFactSequenceInfo(b)}
                    <div class="dossier-belief-card" class:resolved-conflict={b.contradicting_fact_ids.length > 0 || b.version > 1}>
                      <div class="dossier-belief-header">
                        <span class="dossier-attribute-label">{b.attribute}</span>
                        {#if b.contradicting_fact_ids.length > 0 || b.version > 1}
                          <span class="pill pill-warning" style="font-size: 0.68rem;" title="{b.contradicting_fact_ids.length} contradiction(s) resolved">
                            <Sparkles size={11} /> v{b.version} Resolved
                          </span>
                        {:else}
                          <span class="pill pill-neutral" style="font-size: 0.68rem;">
                            v{b.version} Verified
                          </span>
                        {/if}
                      </div>

                      <div class="dossier-belief-value">{b.value}</div>

                      <div class="dossier-source-tag">
                        <span class="seq-num-badge">#{info.sequenceNum < 9999 ? info.sequenceNum : '?'}</span>
                        <span class="fact-tag origin" title="Origin Fact">Fact {info.originFactId}</span>
                        {#if info.hasEvolution && info.allFactIds.length > 1}
                          <span style="color: var(--text-muted); font-size: 0.65rem;">→</span>
                          <span class="fact-tag latest" title="Latest updating fact">Fact {info.latestFactId} (Updated)</span>
                        {/if}
                      </div>

                      <div class="dossier-footer">
                        <div style="display: flex; align-items: center; gap: 0.45rem;">
                          <span style="font-size: 0.76rem; font-weight: 600;">{(b.confidence * 100).toFixed(0)}%</span>
                          <div class="confidence-track" style="width: 45px; height: 5px;">
                            <div class="confidence-fill" style="width: {b.confidence * 100}%;"></div>
                          </div>
                        </div>

                        <button
                          class="btn btn-secondary"
                          style="padding: 0.28rem 0.6rem; font-size: 0.72rem;"
                          onclick={() => openProvenance(b.id)}
                        >
                          <History size={11} /> Provenance
                        </button>
                      </div>
                    </div>
                  {/each}
                </div>
              </div>
            {/each}
          </div>

        <!-- Mode 2: Table View -->
        {:else if repositoryDisplayMode === 'table'}
          <div class="entity-dossier-table-wrapper" style="margin-top: 0.5rem; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg);">
            <table class="entity-dossier-table">
              <thead>
                <tr>
                  <th style="width: 14%;">Entity</th>
                  <th style="width: 18%;">Attribute</th>
                  <th style="width: 32%;">Established Ground Truth</th>
                  <th style="width: 12%;">Source / Seq</th>
                  <th style="width: 10%;">Confidence</th>
                  <th style="width: 8%;">Status</th>
                  <th style="width: 6%; text-align: right;">Audit</th>
                </tr>
              </thead>
              <tbody>
                {#each visibleBeliefs as b}
                  {@const info = getFactSequenceInfo(b)}
                  <tr>
                    <td>
                      <strong style="color: var(--text-primary);">{b.entity}</strong>
                    </td>
                    <td>
                      <span style="font-weight: 600; color: var(--text-secondary);">{b.attribute}</span>
                    </td>
                    <td>
                      <span class="belief-value" style="display: inline-block; max-width: 100%;">
                        {b.value}
                      </span>
                    </td>
                    <td>
                      <div style="display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap;">
                        <span class="seq-num-badge">#{info.sequenceNum < 9999 ? info.sequenceNum : '?'}</span>
                        <span class="fact-tag origin">{info.originFactId}</span>
                        {#if info.hasEvolution && info.allFactIds.length > 1}
                          <span style="color: var(--text-muted); font-size: 0.65rem;">→</span>
                          <span class="fact-tag latest">{info.latestFactId}</span>
                        {/if}
                      </div>
                    </td>
                    <td>
                      <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 0.78rem; font-weight: 600; min-width: 32px;">{(b.confidence * 100).toFixed(0)}%</span>
                        <div class="confidence-track" style="width: 50px; height: 5px;">
                          <div class="confidence-fill" style="width: {b.confidence * 100}%;"></div>
                        </div>
                      </div>
                    </td>
                    <td>
                      {#if b.contradicting_fact_ids.length > 0 || b.version > 1}
                        <span class="pill pill-warning" style="font-size: 0.68rem;">
                          ⚡ v{b.version} Resolved
                        </span>
                      {:else}
                        <span class="pill pill-neutral" style="font-size: 0.68rem;">
                          v{b.version} Clean
                        </span>
                      {/if}
                    </td>
                    <td style="text-align: right;">
                      <button
                        class="btn btn-secondary"
                        style="padding: 0.3rem 0.65rem; font-size: 0.75rem;"
                        onclick={() => openProvenance(b.id)}
                      >
                        <History size={12} />
                      </button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

        <!-- Mode 3: Flat Card Grid -->
        {:else}
          <div class="beliefs-grid" style="margin-top: 0.5rem;">
            {#each visibleBeliefs as b}
              {@const info = getFactSequenceInfo(b)}
              <div class="belief-card" class:has-conflicts={b.contradicting_fact_ids.length > 0 || b.version > 1}>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.45rem;">
                  <div style="display: flex; align-items: center; gap: 0.35rem;">
                    <span class="seq-num-badge">#{info.sequenceNum < 9999 ? info.sequenceNum : '?'}</span>
                    <span class="fact-tag origin" title="Origin Fact">Fact {info.originFactId}</span>
                  </div>
                  {#if b.contradicting_fact_ids.length > 0 || b.version > 1}
                    <span class="pill pill-warning" style="font-size: 0.68rem;">⚡ v{b.version}</span>
                  {:else}
                    <span class="pill pill-neutral" style="font-size: 0.68rem;">v{b.version}</span>
                  {/if}
                </div>

                <div>
                  <div class="belief-entity">{b.entity}</div>
                  <div class="belief-attribute">{b.attribute}</div>
                </div>

                {#if info.hasEvolution && info.allFactIds.length > 1}
                  <div class="fact-trail-strip" title="Sequential fact evolution history">
                    <span style="font-size: 0.68rem; color: var(--text-muted); font-weight: 600;">Chain:</span>
                    {#each info.allFactIds as fid, idx}
                      {#if idx > 0}<span class="trail-arrow">→</span>{/if}
                      <span class="fact-trail-pill" class:active-fact={fid === info.latestFactId}>{fid}</span>
                    {/each}
                  </div>
                {/if}

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

              <div style="font-size: 0.88rem; line-height: 1.4;">{c.description}</div>

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
                  <div style="font-size: 0.82rem; color: var(--text-secondary); line-height: 1.35;">
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

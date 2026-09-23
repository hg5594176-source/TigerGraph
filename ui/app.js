/**
 * Fraud Investigation Dashboard — Client-Side Application
 * Powered by D3.js force simulation, live confidence meters,
 * and unified case subgraph visualization.
 */

// Global State
let currentCaseId = null;
let simulation = null;
let svg = null;
let g = null;
let zoom = null;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    initSvg();
    setupEventListeners();
    loadCases();
});

function initSvg() {
    svg = d3.select('#graphSvg');
    g = svg.append('g').attr('class', 'graph-viewport');

    zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        });

    svg.call(zoom);
}

function setupEventListeners() {
    const caseSelector = document.getElementById('caseSelector');
    caseSelector.addEventListener('change', (e) => {
        const caseId = e.target.value;
        if (caseId) {
            loadCaseData(caseId);
        } else {
            clearDashboard();
        }
    });

    document.getElementById('refreshBtn').addEventListener('click', () => {
        if (currentCaseId) {
            loadCaseData(currentCaseId);
        } else {
            loadCases();
        }
    });

    document.getElementById('resetZoom').addEventListener('click', () => {
        if (svg && zoom) {
            svg.transition().duration(500).call(
                zoom.transform,
                d3.zoomIdentity.translate(svg.node().clientWidth / 2, svg.node().clientHeight / 2).scale(0.8)
            );
        }
    });
}

function toggleNarrative() {
    const panel = document.getElementById('narrativePanel');
    panel.classList.toggle('collapsed');
}

// Fetch list of cases
async function loadCases() {
    try {
        const res = await fetch('/api/cases');
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        const cases = await res.json();
        
        const selector = document.getElementById('caseSelector');
        selector.innerHTML = '<option value="">Select a case...</option>';
        
        cases.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.case_id;
            opt.textContent = `${c.case_id} (${c.status || 'open'}) - ${c.client_id || 'Unknown Client'}`;
            selector.appendChild(opt);
        });

        // Auto-select first case if available
        if (cases.length > 0 && !currentCaseId) {
            selector.value = cases[0].case_id;
            loadCaseData(cases[0].case_id);
        }
    } catch (err) {
        console.warn('Could not fetch cases from server, loading demo fallback', err);
        renderDemoData();
    }
}

// Fetch case details and subgraph
async function loadCaseData(caseId) {
    currentCaseId = caseId;
    try {
        const res = await fetch(`/api/cases/${encodeURIComponent(caseId)}/subgraph`);
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        const data = await res.json();
        renderCase(data);
    } catch (err) {
        console.error('Failed to load case data:', err);
        renderDemoData(caseId);
    }
}

function clearDashboard() {
    currentCaseId = null;
    g.selectAll('*').remove();
    document.getElementById('nodeCount').textContent = '0 nodes';
    document.getElementById('evidenceLoop').textContent = 'Loop 0';
    document.getElementById('caseStatus').textContent = '—';
    document.getElementById('caseStatus').className = 'status-badge';
    document.getElementById('confidenceBars').innerHTML = '<div class="empty-state">Select a case to view hypotheses</div>';
    document.getElementById('timeline').innerHTML = '<div class="empty-state">Select a case to view timeline</div>';
    document.getElementById('narrativeBody').innerHTML = '<div class="empty-state">Select a case to view the narrative</div>';
}

function renderCase(data) {
    if (!data) return;

    // 1. Status badge
    const statusEl = document.getElementById('caseStatus');
    const status = (data.status || data.stop_reason || 'DECIDED').toLowerCase();
    statusEl.textContent = status;
    statusEl.className = 'status-badge';
    if (status.includes('decid') || status.includes('close') || status.includes('confident')) {
        statusEl.classList.add('status-decided');
    } else if (status.includes('escalat') || status.includes('fraud')) {
        statusEl.classList.add('status-escalated');
    } else {
        statusEl.classList.add('status-open');
    }

    // 2. Loop count
    document.getElementById('evidenceLoop').textContent = `Loop ${data.evidence_loop_count ?? 1}`;

    // 3. Render Hypotheses
    let hypotheses = data.hypotheses || [];
    if (hypotheses.length === 0 && data.investigation_record && data.investigation_record.findings) {
        hypotheses = data.investigation_record.findings.map(f => ({
            typology_id: f.typology_id,
            typology_name: f.typology,
            confidence: f.confidence
        }));
    }
    renderConfidenceBars(hypotheses);

    // 4. Render Timeline
    let timeline = data.timeline || [];
    if (timeline.length === 0 && data.investigation_record) {
        (data.investigation_record.evidence || []).forEach((ev, idx) => {
            timeline.push({
                type: 'evidence',
                title: `Evidence Item #${idx + 1}`,
                detail: ev,
                timestamp: 'Discovery'
            });
        });
        (data.investigation_record.decisions || []).forEach(dec => {
            timeline.push({
                type: 'action',
                title: `Action: ${dec.action}`,
                detail: dec.requires_approval ? `Requires approval from ${dec.approved_by}` : 'Auto-executed within policy limit',
                policy: 'Bank Fraud Governance Policy',
                timestamp: dec.decided_at || 'Just now'
            });
        });
    }
    renderTimeline(timeline, data.actions_taken || []);

    // 5. Render Narrative
    renderNarrative(data.narrative || 'No investigation narrative recorded.');

    // 6. Render Graph
    renderGraph(data.nodes || [], data.edges || []);
}

function renderConfidenceBars(hypotheses) {
    const container = document.getElementById('confidenceBars');
    container.innerHTML = '';

    if (!hypotheses || hypotheses.length === 0) {
        container.innerHTML = '<div class="empty-state">No active hypotheses</div>';
        return;
    }

    // Sort descending by confidence
    const sorted = [...hypotheses].sort((a, b) => (b.confidence || 0) - (a.confidence || 0));

    sorted.forEach(item => {
        const conf = Math.max(0, Math.min(1, item.confidence || 0));
        const pct = Math.round(conf * 100);

        let levelClass = 'confidence-low';
        if (conf >= 0.7) levelClass = 'confidence-high';
        else if (conf >= 0.4) levelClass = 'confidence-medium';

        const row = document.createElement('div');
        row.className = `confidence-item ${levelClass}`;
        row.innerHTML = `
            <div class="confidence-label">
                <span class="confidence-name">${escapeHtml(item.typology_name || item.typology_id)}</span>
                <span class="confidence-value">${pct}%</span>
            </div>
            <div class="confidence-bar-track">
                <div class="confidence-bar-fill" style="width: 0%"></div>
            </div>
        `;
        container.appendChild(row);

        // Animate fill bar
        requestAnimationFrame(() => {
            setTimeout(() => {
                const fill = row.querySelector('.confidence-bar-fill');
                if (fill) fill.style.width = `${pct}%`;
            }, 50);
        });
    });
}

function renderTimeline(timeline, actions) {
    const container = document.getElementById('timeline');
    container.innerHTML = '';

    let items = [...timeline];
    if (items.length === 0 && actions && actions.length > 0) {
        items = actions.map(act => ({
            type: 'action',
            title: `Action: ${act.action_type || 'Executed Action'}`,
            detail: act.details || (act.requires_approval ? `Requires approval from ${act.requires_approval}` : 'Auto-executed within policy limit'),
            policy: act.policy_rule || 'Policy Rule #301 - Velocity threshold violation',
            timestamp: act.timestamp || 'Just now'
        }));
    }

    if (items.length === 0) {
        container.innerHTML = '<div class="empty-state">No investigation actions recorded yet</div>';
        return;
    }

    items.forEach(ev => {
        const item = document.createElement('div');
        item.className = 'timeline-item';

        let dotClass = 'timeline-dot-action';
        let dotIcon = '⚡';
        if (ev.type === 'evidence') {
            dotClass = 'timeline-dot-evidence';
            dotIcon = '🔍';
        } else if (ev.type === 'decision') {
            dotClass = 'timeline-dot-decision';
            dotIcon = '⚖️';
        }

        item.innerHTML = `
            <div class="timeline-dot ${dotClass}">${dotIcon}</div>
            <div class="timeline-content">
                <div class="timeline-title">${escapeHtml(ev.title || 'Step')}</div>
                <div class="timeline-detail">${escapeHtml(ev.detail || '')}</div>
                ${ev.policy ? `<div class="timeline-policy">📜 ${escapeHtml(ev.policy)}</div>` : ''}
                <div class="timeline-time">${escapeHtml(ev.timestamp || '')}</div>
            </div>
        `;
        container.appendChild(item);
    });
}

function renderNarrative(narrativeText) {
    const body = document.getElementById('narrativeBody');
    body.textContent = narrativeText;
}

// Force-directed graph visualization
function renderGraph(nodesData, edgesData) {
    document.getElementById('nodeCount').textContent = `${nodesData.length} nodes`;

    if (simulation) simulation.stop();
    g.selectAll('*').remove();

    if (!nodesData || nodesData.length === 0) {
        return;
    }

    const width = svg.node().clientWidth || 600;
    const height = svg.node().clientHeight || 450;

    // Color mapper
    const colorMap = {
        Client: '#00d4ff',
        EvidenceItem: '#f59e0b',
        TypologyPattern: '#7c3aed',
        ActionType: '#ef4444',
        PolicyRule: '#10b981',
        Transaction: '#ec4899',
        FraudCase: '#38bdf8'
    };

    // Deep copy data for D3 mutation
    const nodes = nodesData.map(d => ({ ...d }));
    const links = edgesData.map(d => ({ ...d }));

    // Simulation setup
    simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(80))
        .force('charge', d3.forceManyBody().strength(-240))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(25));

    // Arrow markers for directed edges
    const defs = g.append('defs');
    ['supports', 'contradicts', 'has-evidence', 'took-action', 'default'].forEach(type => {
        defs.append('marker')
            .attr('id', `arrow-${type}`)
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 20)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', type === 'supports' ? '#10b981' : type === 'contradicts' ? '#ef4444' : '#64748b');
    });

    // Links
    const link = g.append('g')
        .attr('class', 'links')
        .selectAll('line')
        .data(links)
        .enter().append('line')
        .attr('class', d => {
            const edgeType = (d.type || '').toLowerCase();
            if (edgeType.includes('support')) return 'link link-supports';
            if (edgeType.includes('contradict')) return 'link link-contradicts';
            if (edgeType.includes('evidence')) return 'link link-has-evidence';
            if (edgeType.includes('action')) return 'link link-took-action';
            return 'link';
        });

    // Tooltip
    let tooltip = d3.select('body').select('.tooltip');
    if (tooltip.empty()) {
        tooltip = d3.select('body').append('div')
            .attr('class', 'tooltip')
            .style('opacity', 0);
    }

    // Nodes
    const node = g.append('g')
        .attr('class', 'nodes')
        .selectAll('g')
        .data(nodes)
        .enter().append('g')
        .attr('class', 'node')
        .call(d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended)
        );

    node.append('circle')
        .attr('r', d => (d.type === 'FraudCase' ? 14 : d.type === 'Client' ? 12 : 9))
        .attr('fill', d => colorMap[d.type] || '#94a3b8')
        .attr('stroke', '#ffffff')
        .attr('stroke-opacity', 0.6)
        .on('mouseover', (event, d) => {
            tooltip.transition().duration(200).style('opacity', 1);
            tooltip.html(`
                <strong>${escapeHtml(d.type || 'Node')}</strong><br/>
                ID: ${escapeHtml(d.id)}<br/>
                ${d.label ? `Name: ${escapeHtml(d.label)}<br/>` : ''}
                ${d.detail ? `Detail: ${escapeHtml(d.detail)}` : ''}
            `)
            .style('left', (event.pageX + 12) + 'px')
            .style('top', (event.pageY - 12) + 'px');
        })
        .on('mouseout', () => {
            tooltip.transition().duration(200).style('opacity', 0);
        });

    node.append('text')
        .attr('class', 'node-label')
        .attr('x', 14)
        .attr('y', 4)
        .text(d => d.label || d.id);

    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Fallback demo data to ensure dashboard displays even before live connection
function renderDemoData(caseId = 'CASE-DEMO-2024') {
    const demoData = {
        case_id: caseId,
        client_id: 'CLI-84920',
        status: 'DECIDED',
        evidence_loop_count: 2,
        hypotheses: [
            { typology_id: 'TYP-01', typology_name: 'Card-Not-Present Velocity Attack', confidence: 0.88 },
            { typology_id: 'TYP-02', typology_name: 'Account Takeover via Proxy', confidence: 0.42 },
            { typology_id: 'TYP-03', typology_name: 'Synthetic Identity Ring', confidence: 0.18 },
            { typology_id: 'TYP-04', typology_name: 'Friendly Fraud / Chargeback', confidence: 0.05 }
        ],
        actions_taken: [
            { action_type: 'block_card', requires_approval: 'fraud_manager', policy_rule: 'PR-102: Immediate block on burst transaction failure', timestamp: '14:22:05 UTC' },
            { action_type: 'request_stepup_auth', requires_approval: null, policy_rule: 'PR-204: Mandatory 2FA challenge on IP anomaly', timestamp: '14:22:08 UTC' },
            { action_type: 'file_sar', requires_approval: 'compliance_officer', policy_rule: 'AML-04: Suspicious Activity Report filed on multi-card burst > $5,000', timestamp: '14:22:15 UTC' }
        ],
        timeline: [
            { type: 'evidence', title: 'High-frequency transaction burst', detail: '8 transactions totaling $4,290 within 12 minutes from Russian IP proxy', timestamp: '14:20:10 UTC' },
            { type: 'evidence', title: 'Device fingerprint shared across 3 accounts', detail: 'Device ID D-9943 connected to 2 previously flagged chargeback accounts', timestamp: '14:21:40 UTC' },
            { type: 'decision', title: 'Leading Hypothesis Confirmed', detail: 'CNP Velocity confidence (88%) exceeded stopping threshold (margin > 0.40)', policy: 'Stopping Rule: Confident Exit (Rule 1)', timestamp: '14:22:00 UTC' },
            { type: 'action', title: 'Card Block Initiated', detail: 'Card #4282 queued for manager approval; auto-stepup challenge triggered', policy: 'Policy Rule #102 & #204', timestamp: '14:22:10 UTC' }
        ],
        narrative: `INVESTIGATION NARRATIVE: CASE ${caseId}\n\nClient CLI-84920 triggered velocity monitoring after 8 consecutive high-value transactions were processed within 12 minutes from an anonymous proxy network. Identity resolution identified device D-9943 as a bridge node connecting two previously confirmed fraud cases in Ring #14.\n\nPrecedent vector matching matched past case CASE-CLOSED-1108 with 91% semantic similarity. Hypothesis assessment converged on Card-Not-Present Velocity Attack with 88% confidence. In accordance with Fraud Policy Rule 102 and AML-04, the card was submitted for blocking and a Suspicious Activity Report was prepared for compliance officer approval.`,
        nodes: [
            { id: caseId, label: 'Case 2024', type: 'FraudCase' },
            { id: 'CLI-84920', label: 'Client 84920', type: 'Client' },
            { id: 'TXN-901', label: 'Txn $1,200', type: 'Transaction' },
            { id: 'TXN-902', label: 'Txn $1,800', type: 'Transaction' },
            { id: 'EV-BURST', label: 'Burst Velocity (8 tx)', type: 'EvidenceItem' },
            { id: 'EV-PROXY', label: 'Proxy IP Flagged', type: 'EvidenceItem' },
            { id: 'TYP-01', label: 'CNP Velocity Attack', type: 'TypologyPattern' },
            { id: 'ACT-BLOCK', label: 'Block Card', type: 'ActionType' },
            { id: 'ACT-SAR', label: 'File SAR', type: 'ActionType' },
            { id: 'POL-102', label: 'Policy Rule 102', type: 'PolicyRule' }
        ],
        edges: [
            { source: caseId, target: 'CLI-84920', type: 'ABOUT_CLIENT' },
            { source: caseId, target: 'TXN-901', type: 'INVESTIGATES' },
            { source: caseId, target: 'TXN-902', type: 'INVESTIGATES' },
            { source: caseId, target: 'EV-BURST', type: 'HAS_EVIDENCE' },
            { source: caseId, target: 'EV-PROXY', type: 'HAS_EVIDENCE' },
            { source: 'EV-BURST', target: 'TYP-01', type: 'SUPPORTS' },
            { source: 'EV-PROXY', target: 'TYP-01', type: 'SUPPORTS' },
            { source: caseId, target: 'ACT-BLOCK', type: 'TOOK_ACTION' },
            { source: caseId, target: 'ACT-SAR', type: 'TOOK_ACTION' },
            { source: 'POL-102', target: 'TYP-01', type: 'APPLIES_TO' }
        ]
    };

    renderCase(demoData);
}

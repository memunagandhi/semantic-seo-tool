document.addEventListener('DOMContentLoaded', () => {
  const passagesContainer = document.getElementById('passages-container');
  const btnAddPassage = document.getElementById('btn-add-passage');
  const passageCountPill = document.getElementById('passage-count-pill');
  const analyzeForm = document.getElementById('analyze-form');
  const btnSubmit = document.getElementById('btn-submit');
  const btnText = btnSubmit?.querySelector('.btn-text');
  const btnLoader = btnSubmit?.querySelector('.btn-loader');
  
  const emptyState = document.getElementById('empty-state');
  const liveResults = document.getElementById('live-results');
  const btnLoadDemo = document.getElementById('btn-load-demo');
  const btnEmptyDemo = document.getElementById('btn-empty-demo');

  // Cold Chain Demo Data
  const DEMO_QUERY = "What temperature is required for pharmaceutical cold chain shipping?";
  const DEMO_PASSAGES = [
    "Pharmaceutical cold chain shipping requires strict product-appropriate temperature monitoring, documented custody handoffs, and regulatory compliance throughout transit to prevent degradation.",
    "Temperature-controlled fleet management utilizes specialized refrigerated vehicles equipped with real-time telematics and automated exception alert systems for perishable cargo.",
    "Refrigerated transport and cold storage facilities maintain multi-zone thermal integrity from pre-cooling stages through line-haul movement and final delivery."
  ];

  // 1. Update Passage Count Pill
  function updatePassageCount() {
    const cards = passagesContainer.querySelectorAll('.passage-card');
    if (passageCountPill) {
      passageCountPill.textContent = `${cards.length} Passage${cards.length === 1 ? '' : 's'}`;
    }
  }

  // 2. Add New Passage Card
  if (btnAddPassage) {
    btnAddPassage.addEventListener('click', () => {
      const cards = passagesContainer.querySelectorAll('.passage-card');
      const nextIndex = cards.length + 1;
      const newCard = document.createElement('div');
      newCard.className = 'passage-card';
      newCard.dataset.index = nextIndex;
      newCard.innerHTML = `
        <div class="passage-card-header">
          <span class="passage-label">Passage #${nextIndex}</span>
          <button type="button" class="btn-remove-passage" title="Remove passage">✕</button>
        </div>
        <textarea class="passage-textarea" placeholder="Paste paragraph or section content here..."></textarea>
      `;
      passagesContainer.appendChild(newCard);
      attachRemoveHandler(newCard.querySelector('.btn-remove-passage'));
      updatePassageCount();
    });
  }

  // 3. Remove Passage Handler
  function attachRemoveHandler(btn) {
    if (!btn) return;
    btn.addEventListener('click', (e) => {
      const card = e.target.closest('.passage-card');
      const totalCards = passagesContainer.querySelectorAll('.passage-card').length;
      if (totalCards <= 1) {
        alert("You must keep at least one passage to analyze.");
        return;
      }
      card.remove();
      // Renumber
      passagesContainer.querySelectorAll('.passage-card').forEach((c, idx) => {
        c.dataset.index = idx + 1;
        c.querySelector('.passage-label').textContent = `Passage #${idx + 1}`;
      });
      updatePassageCount();
    });
  }

  document.querySelectorAll('.btn-remove-passage').forEach(attachRemoveHandler);

  // 4. Load Demo Data
  function loadDemo() {
    const queryInput = document.getElementById('search-query');
    if (queryInput) queryInput.value = DEMO_QUERY;

    // Reset cards to match demo
    passagesContainer.innerHTML = '';
    DEMO_PASSAGES.forEach((text, i) => {
      const idx = i + 1;
      const card = document.createElement('div');
      card.className = 'passage-card';
      card.dataset.index = idx;
      card.innerHTML = `
        <div class="passage-card-header">
          <span class="passage-label">Passage #${idx}</span>
          <button type="button" class="btn-remove-passage" title="Remove passage">✕</button>
        </div>
        <textarea class="passage-textarea">${text}</textarea>
      `;
      passagesContainer.appendChild(card);
      attachRemoveHandler(card.querySelector('.btn-remove-passage'));
    });
    updatePassageCount();
  }

  if (btnLoadDemo) btnLoadDemo.addEventListener('click', loadDemo);
  if (btnEmptyDemo) btnEmptyDemo.addEventListener('click', loadDemo);

  // 5. Submit Form & AJAX Call
  if (analyzeForm) {
    analyzeForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      const queryInput = document.getElementById('search-query');
      const query = queryInput ? queryInput.value.trim() : '';
      const textareas = passagesContainer.querySelectorAll('.passage-textarea');
      const passages = Array.from(textareas).map(t => t.value.trim()).filter(Boolean);

      if (!query) {
        alert("Please enter a target search query.");
        return;
      }
      if (passages.length === 0) {
        alert("Please enter at least one passage to analyze.");
        return;
      }

      // UI Loading state
      btnSubmit.disabled = true;
      if (btnText) btnText.style.display = 'none';
      if (btnLoader) btnLoader.style.display = 'inline';

      try {
        const response = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, passages })
        });

        const data = await response.json();

        if (data.success) {
          renderResults(data);
        } else {
          alert("Error running analysis: " + (data.error || "Unknown server error"));
        }
      } catch (err) {
        alert("Network error: Could not reach analysis engine.");
      } finally {
        btnSubmit.disabled = false;
        if (btnText) btnText.style.display = 'inline';
        if (btnLoader) btnLoader.style.display = 'none';
      }
    });
  }

  // 6. Render Results to UI
  function renderResults(data) {
    if (emptyState) emptyState.style.display = 'none';
    if (liveResults) liveResults.style.display = 'block';

    const winner = data.winner;
    const topPercent = Math.round(winner.rerank_score * 100);

    // Update Circle Gauge
    const circlePath = document.getElementById('score-circle-path');
    const scoreNum = document.getElementById('winner-score-num');
    if (circlePath) circlePath.setAttribute('stroke-dasharray', `${topPercent}, 100`);
    if (scoreNum) scoreNum.textContent = `${topPercent}%`;

    // Winner Info
    const winnerBadge = document.getElementById('winner-verdict-badge');
    const winnerText = document.getElementById('winner-text');
    if (winnerBadge) {
      winnerBadge.textContent = `Featured Winner (Passage #${winner.original_index + 1}) — ${data.verdict}`;
    }
    if (winnerText) winnerText.textContent = winner.document;

    // Table Populate
    const tbody = document.getElementById('matrix-tbody');
    if (tbody) {
      tbody.innerHTML = '';
      data.comparison_table.forEach(item => {
        const tr = document.createElement('tr');
        
        let shiftBadge = '';
        if (item.rank_shift > 0) {
          shiftBadge = `<span class="badge-shift shift-up">▲ +${item.rank_shift}</span>`;
        } else if (item.rank_shift < 0) {
          shiftBadge = `<span class="badge-shift shift-down">▼ ${item.rank_shift}</span>`;
        } else {
          shiftBadge = `<span class="badge-shift shift-same">▬ Unchanged</span>`;
        }

        tr.innerHTML = `
          <td><strong>#${item.original_index + 1}</strong></td>
          <td>${(item.dense_similarity * 100).toFixed(1)}% (Rank #${item.initial_dense_rank})</td>
          <td><strong>${(item.rerank_score * 100).toFixed(1)}%</strong> (Pos #${item.post_rerank_position})</td>
          <td>${shiftBadge}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    // Topical Gap Alert Box
    const gapCard = document.getElementById('topical-gap-card');
    const tagsBox = document.getElementById('missing-tags-box');
    const adviceText = document.getElementById('gap-advice-text');

    if (gapCard && tagsBox) {
      tagsBox.innerHTML = '';
      if (data.missing_entities && data.missing_entities.length > 0) {
        gapCard.style.display = 'block';
        data.missing_entities.forEach(tag => {
          const pill = document.createElement('span');
          pill.className = 'missing-pill';
          pill.textContent = `Missing: ${tag}`;
          tagsBox.appendChild(pill);
        });
      } else {
        tagsBox.innerHTML = '<span style="color: var(--emerald); font-weight: 600;">✓ No missing entities! Full topical coverage.</span>';
      }

      if (adviceText) {
        adviceText.innerHTML = `<strong>Copy Optimization Suggestion:</strong> ${data.copy_advice}`;
      }
    }

    // Smooth scroll into results if mobile
    if (window.innerWidth <= 1024) {
      liveResults.scrollIntoView({ behavior: 'smooth' });
    }
  }

});

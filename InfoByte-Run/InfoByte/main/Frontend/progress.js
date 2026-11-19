(() => {
  'use strict';

  const status = document.querySelector('#progress-status');
  const topicList = document.querySelector('#topic-list');
  const recentList = document.querySelector('#recent-list');
  const topicsEmpty = document.querySelector('#topics-empty');
  const recentEmpty = document.querySelector('#recent-empty');

  function element(tag, text = '') {
    const node = document.createElement(tag);
    node.textContent = text;
    return node;
  }

  function redirectToLogin() {
    const next = window.location.pathname + window.location.search;
    window.location.replace('/infobyte-auth/login.html?next=' + encodeURIComponent(next));
  }

  function formatDate(value) {
    if (!value) return 'Күні көрсетілмеген';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Күні көрсетілмеген';
    return new Intl.DateTimeFormat('kk-KZ', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
  }

  function renderSummary(summary) {
    document.querySelector('#tests-completed').textContent = summary.tests_completed ?? 0;
    document.querySelector('#accuracy').textContent = `${summary.accuracy ?? 0}%`;
    document.querySelector('#best-result').textContent = `${summary.best_percent ?? 0}%`;
    document.querySelector('#in-progress').textContent = summary.tests_in_progress ?? 0;
    document.querySelector('#answer-ratio').textContent = `${summary.correct_answers ?? 0} / ${summary.questions_answered ?? 0}`;
  }

  function renderTopics(topics) {
    topicList.replaceChildren();
    const list = Array.isArray(topics) ? topics : [];
    topicsEmpty.hidden = list.length > 0;
    list.forEach(item => {
      const row = element('article');
      row.className = 'topic-item';
      const head = element('div');
      head.className = 'topic-head';
      head.append(element('span', item.subject || 'Тақырып'), element('span', `${item.percent ?? 0}%`));
      head.children[0].className = 'topic-name';
      head.children[1].className = 'topic-score';
      const track = element('div');
      track.className = 'topic-track';
      track.setAttribute('role', 'progressbar');
      track.setAttribute('aria-label', `${item.subject || 'Тақырып'} бойынша дәлдік`);
      track.setAttribute('aria-valuemin', '0');
      track.setAttribute('aria-valuemax', '100');
      track.setAttribute('aria-valuenow', String(item.percent ?? 0));
      const fill = element('div');
      fill.className = 'topic-fill';
      fill.style.width = `${Math.max(0, Math.min(100, Number(item.percent) || 0))}%`;
      track.append(fill);
      const foot = element('div');
      foot.className = 'topic-foot';
      foot.append(element('span', `${item.correct ?? 0} дұрыс жауап`), element('span', `${item.total ?? 0} сұрақ`));
      row.append(head, track, foot);
      topicList.append(row);
    });
  }

  function renderRecent(attempts) {
    recentList.replaceChildren();
    const list = Array.isArray(attempts) ? attempts : [];
    recentEmpty.hidden = list.length > 0;
    list.forEach(attempt => {
      const row = element('article');
      row.className = 'recent-row';
      row.append(element('span', attempt.topic || 'Тест'));
      row.children[0].className = 'recent-topic';
      row.append(element('time', formatDate(attempt.finished_at || attempt.started_at)));
      row.children[1].className = 'recent-date';
      if (attempt.finished_at) row.children[1].dateTime = attempt.finished_at;
      const result = element('span', `${attempt.correct}/${attempt.total} · ${attempt.percent}%`);
      result.className = 'recent-result';
      row.append(result);
      recentList.append(row);
    });
  }

  async function loadProgress() {
    try {
      const response = await fetch('/api/progress', { credentials: 'same-origin', cache: 'no-store' });
      if (response.status === 401) {
        redirectToLogin();
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Прогресс мәліметін жүктеу мүмкін болмады.');
      renderSummary(data.summary || {});
      renderTopics(data.topics || []);
      renderRecent(data.recent_attempts || []);
      status.textContent = '';
    } catch (error) {
      status.textContent = error.message || 'Серверге қосылу мүмкін болмады. Бетті жаңартып көріңіз.';
      status.classList.add('is-error');
      topicsEmpty.hidden = false;
      topicsEmpty.textContent = 'Тақырыптық көрсеткіштерді жүктеу мүмкін болмады.';
      recentEmpty.hidden = false;
      recentEmpty.textContent = 'Тест тарихын жүктеу мүмкін болмады.';
    } finally {
      topicList.setAttribute('aria-busy', 'false');
      recentList.setAttribute('aria-busy', 'false');
    }
  }

  loadProgress();
})();

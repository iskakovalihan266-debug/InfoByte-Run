const screen = document.querySelector('#screen');
const errorBox = document.querySelector('#error');
const letters = 'ABCD';
let attempt = null;
let attemptId = null;
let questionIndex = 0;
let busy = false;

function el(tag, text = '') {
  const node = document.createElement(tag);
  node.textContent = text;
  return node;
}

async function api(path, method = 'GET', body) {
  const options = { method, credentials: 'same-origin', cache: 'no-store' };
  if (body !== undefined) {
    options.headers = { 'Content-Type': 'application/json' };
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  if (response.status === 401) {
    const next = window.location.pathname + window.location.search;
    window.location.replace('/infobyte-auth/login.html?next=' + encodeURIComponent(next));
    throw new Error('Аккаунтқа кіріңіз.');
  }
  const contentType = response.headers.get('content-type') || '';
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data && typeof data === 'object' ? data.detail : null;
    const fallback = contentType.includes('application/json')
      ? `Сұрау орындалмады (HTTP ${response.status}).`
      : `Сервер JSON емес жауап қайтарды (HTTP ${response.status}).`;
    throw new Error(detail || fallback);
  }
  if (data === null) throw new Error(`Сервер жарамды JSON қайтармады (HTTP ${response.status}).`);
  return data;
}

async function run(action) {
  if (busy) return;
  busy = true;
  screen.inert = true;
  errorBox.textContent = '';
  try {
    await action();
  } catch (error) {
    errorBox.textContent = error.message || 'Қате пайда болды. Қайта көріңіз.';
  } finally {
    busy = false;
    screen.inert = false;
  }
}

function button(text, action, options = {}) {
  const node = el('button', text);
  node.type = 'button';
  if (options.primary) node.classList.add('primary');
  if (options.className) node.classList.add(options.className);
  node.disabled = Boolean(options.disabled);
  node.addEventListener('click', () => run(action));
  return node;
}

function setUrl(view, index) {
  if (!attemptId) return;
  const params = new URLSearchParams({ attempt: attemptId, view });
  if (view === 'review') params.set('question', String(index));
  window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`);
}

function formatDate(value) {
  if (!value) return 'Күні көрсетілмеген';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Күні көрсетілмеген';
  return new Intl.DateTimeFormat('kk-KZ', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

function selectField(parent, labelText, values) {
  const label = el('label', labelText);
  label.className = 'field';
  const field = el('select');
  for (const [value, text] of values) field.add(new Option(text, value));
  label.append(field);
  parent.append(label);
  return field;
}

function clearAttemptUrl() {
  attempt = null;
  attemptId = null;
  questionIndex = 0;
  window.history.replaceState({}, '', window.location.pathname);
}

async function home() {
  clearAttemptUrl();
  const [topics, completed] = await Promise.all([
    api('/api/test-topics'),
    api('/api/me/attempts')
  ]);

  const selection = el('section');
  selection.className = 'panel';
  const heading = el('h2', 'Жаңа тестті бастау');
  const copy = el('p', 'Тақырып пен сұрақ санын таңдап, тестті бастаңыз.');
  copy.className = 'section-copy';
  selection.append(heading, copy);

  const fields = el('div');
  fields.className = 'selection-grid';
  const topic = selectField(fields, 'Тақырып', [
    ['0', 'Аралас тест'],
    ...topics.map((name, index) => [String(index + 1), name])
  ]);
  const count = selectField(fields, 'Сұрақ саны', [[5, '5 сұрақ'], [10, '10 сұрақ'], [20, '20 сұрақ']]);
  selection.append(fields);

  const footer = el('div');
  footer.className = 'panel-footer';
  footer.append(button('Тестті бастау', async () => {
    const created = await api(`/api/tests/${Number(topic.value)}/attempts`, 'POST', {
      count: Number(count.value)
    });
    attempt = created;
    attemptId = created.id;
    questionIndex = 0;
    setUrl('quiz', 0);
    renderQuiz();
  }, { primary: true }));
  selection.append(footer);

  const historyPanel = el('section');
  historyPanel.className = 'panel';
  const historyHeading = el('div');
  historyHeading.className = 'section-heading';
  historyHeading.append(el('h2', 'Менің өткен тесттерім'));
  historyPanel.append(historyHeading);

  if (!completed.length) {
    const empty = el('p', 'Аяқталған тесттеріңіз осында сақталады.');
    empty.className = 'empty-state';
    historyPanel.append(empty);
  } else {
    const list = el('div');
    list.className = 'history-list';
    for (const item of completed) {
      const row = el('article');
      row.className = 'history-row';
      const title = el('div');
      const name = el('span', item.test_title);
      name.className = 'history-title';
      const date = el('time', formatDate(item.finished_at));
      date.className = 'history-date';
      date.dateTime = item.finished_at;
      title.append(name, date);
      const score = el('span', `${item.score} / ${item.question_count} ұпай · ${item.percent}%`);
      score.className = 'history-score';
      row.append(title, score, button('Нәтижені ашу', () => openAttempt(item.id, 'result')));
      list.append(row);
    }
    historyPanel.append(list);
  }
  screen.replaceChildren(selection, historyPanel);
}

async function openAttempt(id, requestedView = 'result', requestedQuestion = 0) {
  const data = await api(`/api/attempts/${encodeURIComponent(id)}`);
  attempt = data;
  attemptId = data.id;
  if (data.status === 'completed') {
    if (requestedView === 'review') {
      questionIndex = Math.max(0, Math.min(requestedQuestion, data.questions.length - 1));
      setUrl('review', questionIndex);
      renderReview();
    } else {
      setUrl('result', 0);
      renderResult();
    }
  } else {
    const firstUnanswered = data.questions.findIndex(question => question.selected_option_index == null);
    questionIndex = Math.max(0, firstUnanswered >= 0 ? firstUnanswered : 0);
    setUrl('quiz', questionIndex);
    renderQuiz();
  }
}

async function startRetry() {
  const created = await api(`/api/attempts/${encodeURIComponent(attemptId)}/retry-mistakes`, 'POST');
  attempt = created;
  attemptId = created.id;
  questionIndex = 0;
  setUrl('quiz', 0);
  renderQuiz();
}

function renderQuiz() {
  if (!attempt || !attempt.questions.length) return;
  const question = attempt.questions[questionIndex];
  const card = el('section');
  card.className = 'review-card';

  const heading = el('div');
  heading.className = 'review-head';
  const title = el('div');
  title.append(el('p', attempt.test_title), el('h2', 'Тест тапсыру'));
  title.children[0].className = 'card-kicker';
  heading.append(title, el('span', `${questionIndex + 1} / ${attempt.question_count} сұрақ`));
  heading.children[1].className = 'review-count';

  const progress = el('progress');
  progress.max = attempt.question_count;
  progress.value = questionIndex + 1;
  progress.setAttribute('aria-label', 'Тесттегі сұрақ реті');
  progress.style.width = '100%';

  const prompt = el('p', question.text);
  prompt.className = 'review-question';
  const options = el('div');
  options.className = 'review-options';
  question.options.forEach((text, index) => {
    const choice = button(`${letters[index] || index + 1}) ${text}`, async () => {
      question.selected_option_index = index;
      renderQuiz();
      const updated = await api(`/api/attempts/${encodeURIComponent(attemptId)}/answers`, 'PATCH', {
        question_id: question.question_id,
        selected_option_index: index
      });
      attempt = updated;
      renderQuiz();
    });
    choice.classList.add('answer-choice');
    choice.setAttribute('aria-pressed', String(question.selected_option_index === index));
    if (question.selected_option_index === index) choice.classList.add('is-selected');
    options.append(choice);
  });

  const actions = el('div');
  actions.className = 'actions';
  const previous = button('← Алдыңғы сұрақ', () => {
    questionIndex -= 1;
    setUrl('quiz', questionIndex);
    renderQuiz();
  }, { disabled: questionIndex === 0 });
  const right = el('div');
  right.className = 'actions-end';
  if (questionIndex < attempt.questions.length - 1) {
    right.append(button('Келесі сұрақ →', () => {
      questionIndex += 1;
      setUrl('quiz', questionIndex);
      renderQuiz();
    }, { primary: true }));
  }
  right.append(button('Тестті аяқтау', finishAttempt, { primary: questionIndex === attempt.questions.length - 1 }));
  actions.append(previous, right);

  card.append(heading, progress, prompt, options, actions);
  screen.replaceChildren(card);
}

async function finishAttempt() {
  const answers = attempt.questions.map(question => ({
    question_id: question.question_id,
    selected_option_index: question.selected_option_index ?? null
  }));
  const completed = await api(`/api/attempts/${encodeURIComponent(attemptId)}/submit`, 'POST', { answers });
  attempt = completed;
  setUrl('result', 0);
  renderResult();
}

function resultStatus(question) {
  if (question.status === 'correct') return ['Дұрыс', 'correct'];
  if (question.status === 'unanswered') return ['Жауапсыз', 'unanswered'];
  return ['Қате', 'incorrect'];
}

function renderResult() {
  if (!attempt || attempt.status !== 'completed') return;
  const questions = attempt.questions;
  const score = Number(attempt.score) || 0;
  const total = Number(attempt.question_count) || questions.length;
  const percent = Number(attempt.percent) || 0;
  const incorrect = questions.filter(question => question.status === 'incorrect').length;
  const unanswered = questions.filter(question => question.status === 'unanswered').length;

  const card = el('section');
  card.className = 'result-card';
  const heading = el('div');
  heading.className = 'result-heading';
  heading.append(el('p', attempt.test_title), el('h2', 'Тест нәтижесі'));
  heading.children[0].className = 'card-kicker';

  const overview = el('div');
  overview.className = 'result-overview';
  const ring = el('div');
  ring.className = 'score-ring';
  ring.setAttribute('role', 'img');
  ring.setAttribute('aria-label', `Нәтиже: ${percent}%`);
  ring.style.setProperty('--ring-angle', `${percent * 3.6}deg`);
  const ringValue = el('span', `${percent}%`);
  ringValue.className = 'score-ring-value';
  ring.append(ringValue);

  const stats = el('div');
  stats.className = 'result-stats';
  const scoreLine = el('p');
  scoreLine.className = 'score-line';
  scoreLine.append(document.createTextNode(`${score} / ${total} ұпай `));
  scoreLine.append(el('span', `· ${percent}%`));
  const chips = el('div');
  chips.className = 'stat-row';
  const correctChip = el('span', `Дұрыс ${score}`);
  correctChip.className = 'stat-chip correct';
  const incorrectChip = el('span', `Қате ${incorrect}`);
  incorrectChip.className = 'stat-chip incorrect';
  const unansweredChip = el('span', `Жауапсыз ${unanswered}`);
  unansweredChip.className = 'stat-chip unanswered';
  chips.append(correctChip, incorrectChip, unansweredChip);
  stats.append(scoreLine, chips);
  overview.append(ring, stats);

  const actions = el('div');
  actions.className = 'result-actions';
  actions.append(button('Тестті шолу', () => showReview(0), { primary: true }));
  actions.append(button('Қателерді қайталау', startRetry, {
    disabled: incorrect + unanswered === 0
  }));
  actions.append(button('Жаңа тест', home));

  const listHeading = el('h3', 'Сұрақтар бойынша');
  listHeading.className = 'questions-heading';
  const list = el('div');
  list.className = 'question-list';
  questions.forEach((question, index) => {
    const [label, statusClass] = resultStatus(question);
    const row = button('', () => showReview(index));
    row.classList.add('question-summary');
    const questionTitle = el('span', `${index + 1}-сұрақ`);
    questionTitle.className = 'question-summary-title';
    const badge = el('span', label);
    badge.className = `status-badge ${statusClass}`;
    row.append(questionTitle, badge);
    list.append(row);
  });

  card.append(heading, overview, actions, listHeading, list);
  screen.replaceChildren(card);
}

function showReview(index) {
  questionIndex = Math.max(0, Math.min(index, attempt.questions.length - 1));
  setUrl('review', questionIndex);
  renderReview();
}

function renderReview() {
  if (!attempt || attempt.status !== 'completed') return;
  const question = attempt.questions[questionIndex];
  const card = el('section');
  card.className = 'review-card';

  const heading = el('div');
  heading.className = 'review-head';
  const title = el('div');
  title.append(el('p', attempt.test_title), el('h2', 'Тестті шолу'));
  title.children[0].className = 'card-kicker';
  const count = el('span', `${questionIndex + 1} / ${attempt.question_count} сұрақ`);
  count.className = 'review-count';
  heading.append(title, count);

  const prompt = el('p', question.text);
  prompt.className = 'review-question';
  const options = el('div');
  options.className = 'review-options';
  question.options.forEach((text, index) => {
    const selected = question.selected_option_index === index;
    const correct = question.correct_option_index === index;
    const row = el('div');
    row.className = 'review-option';
    if (selected && !correct) row.classList.add('is-wrong');
    if (correct) row.classList.add('is-correct');
    const letter = el('span', `${letters[index] || index + 1})`);
    letter.className = 'review-option-letter';
    const answerText = el('span', text);
    answerText.className = 'review-option-text';
    row.append(letter, answerText);
    if (selected && correct) row.append(el('span', 'Сіздің жауабыңыз · Дұрыс'));
    else if (selected) row.append(el('span', 'Сіздің жауабыңыз · Қате'));
    else if (correct) row.append(el('span', 'Дұрыс жауап'));
    if (row.lastElementChild !== answerText) row.lastElementChild.className = 'review-option-label';
    options.append(row);
  });

  const correct = question.correct_option_index;
  const answer = el('div');
  answer.className = 'correct-answer';
  answer.append(el('span', 'Дұрыс жауап'));
  answer.children[0].className = 'correct-answer-label';
  answer.append(el('span', `${letters[correct] || correct + 1}) ${question.options[correct]}`));
  answer.children[1].className = 'correct-answer-text';

  if (question.selected_option_index == null) {
    const unanswered = el('p', 'Жауап берілмеді');
    unanswered.className = 'unanswered-note';
    card.append(heading, prompt, options, unanswered, answer);
  } else {
    card.append(heading, prompt, options, answer);
  }

  const actions = el('div');
  actions.className = 'review-actions';
  actions.append(button('← Алдыңғы', () => showReview(questionIndex - 1), {
    disabled: questionIndex === 0
  }));
  const right = el('div');
  right.className = 'review-actions-right';
  right.append(button('Нәтижеге оралу', () => {
    setUrl('result', 0);
    renderResult();
  }));
  if (questionIndex < attempt.questions.length - 1) {
    right.append(button('Келесі →', () => showReview(questionIndex + 1), { primary: true }));
  }
  actions.append(right);
  card.append(actions);
  screen.replaceChildren(card);
}

async function initialize() {
  const params = new URLSearchParams(window.location.search);
  const id = params.get('attempt');
  if (!id) {
    await home();
    return;
  }
  const view = params.get('view') || 'result';
  const parsedQuestion = Number.parseInt(params.get('question') || '0', 10);
  await openAttempt(id, view, Number.isFinite(parsedQuestion) ? parsedQuestion : 0);
}

run(initialize);

const list = document.querySelector('#mistake-list');
const status = document.querySelector('#status');
const summary = document.querySelector('#summary');
const search = document.querySelector('#search');
const filters = [...document.querySelectorAll('[data-filter]')];
const letters = 'ABCD';
let mistakes = [];
let activeFilter = 'all';

document.querySelector('#year').textContent = new Date().getFullYear();

function node(tag, text = '') {
  const element = document.createElement(tag);
  element.textContent = text;
  return element;
}

async function api(path, method = 'GET', body) {
  const options = { method, credentials: 'same-origin' };
  if (body !== undefined) {
    options.headers = { 'Content-Type': 'application/json' };
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  if (response.status === 401) {
    location.replace('/infobyte-auth/login.html');
    throw new Error('Жүйеге кіріп, қайта көріңіз.');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || 'Сұрауды орындау мүмкін болмады.');
  return data;
}

function updateSummary() {
  const reviewed = mistakes.filter(item => item.reviewed).length;
  const values = [mistakes.length, mistakes.length - reviewed, reviewed];
  summary.querySelectorAll('.stat-value').forEach((element, index) => {
    element.textContent = values[index];
  });
}

function matches(item, term) {
  if (activeFilter === 'pending' && item.reviewed) return false;
  if (activeFilter === 'reviewed' && !item.reviewed) return false;
  if (!term) return true;
  const answer = item.options?.[item.selected] || '';
  return [item.question, item.topic, item.analysis, answer]
    .some(value => String(value || '').toLocaleLowerCase('kk').includes(term));
}

function emptyState(title, copy) {
  const box = node('div');
  box.className = 'empty-state';
  box.append(node('div', '✓'));
  box.firstChild.className = 'empty-icon';
  box.append(node('h3', title), node('p', copy));
  return box;
}

function renderCard(item) {
  const card = node('article');
  card.className = 'mistake-card';
  const head = node('div');
  head.className = 'card-head';
  const tags = node('div');
  tags.className = 'tags';
  const topic = node('span', item.topic || 'Тақырып көрсетілмеген');
  topic.className = 'tag';
  const level = node('span', item.level || 'Деңгейі белгісіз');
  level.className = 'tag level';
  tags.append(topic, level);
  const attempt = node('span', `Тест · ${String(item.attempt_id).slice(0, 8)}`);
  attempt.className = 'attempt';
  head.append(tags, attempt);

  const questionNo = node('p', `СҰРАҚ №${item.question_id}`);
  questionNo.className = 'question-number';
  const prompt = node('h3', item.question);
  prompt.className = 'question-text';
  const answers = node('ul');
  answers.className = 'answer-list';
  (item.options || []).forEach((option, index) => {
    const row = node('li');
    row.className = 'answer-option';
    const isWrong = index === item.selected && item.selected !== item.correct;
    const isCorrect = index === item.correct;
    if (isWrong) row.classList.add('is-wrong');
    if (isCorrect) row.classList.add('is-correct');
    const letter = node('span', letters[index] || String(index + 1));
    letter.className = 'answer-letter';
    row.append(letter, node('span', option));
    if (isWrong || isCorrect) {
      const marker = node('span', isWrong ? 'Сіздің жауабыңыз' : 'Дұрыс жауап');
      marker.className = 'answer-marker';
      row.append(marker);
    }
    answers.append(row);
  });

  const analysis = node('div');
  analysis.className = 'analysis';
  analysis.append(node('p', 'Қысқаша талдау'), node('p', item.analysis || 'Дұрыс жауапты салыстырып, осы тақырыптың негізгі ережесін қайталап шығыңыз.'));
  analysis.children[0].className = 'analysis-title';
  analysis.children[1].className = 'analysis-copy';

  const footer = node('div');
  footer.className = 'card-footer';
  const reviewed = Boolean(item.reviewed);
  const button = node('button', reviewed ? '✓ Қаралды' : 'Қайталадым деп белгілеу');
  button.type = 'button';
  button.className = `review-button${reviewed ? ' is-reviewed' : ''}`;
  button.setAttribute('aria-pressed', String(reviewed));
  button.addEventListener('click', async () => {
    button.disabled = true;
    status.classList.remove('is-error');
    status.textContent = '';
    try {
      const updated = await api('/api/mistakes/review', 'POST', {
        attempt_id: item.attempt_id,
        question_id: item.question_id,
        reviewed: !item.reviewed
      });
      const index = mistakes.findIndex(entry => entry.attempt_id === item.attempt_id && entry.question_id === item.question_id);
      if (index !== -1) mistakes[index] = updated;
      updateSummary();
      render();
      status.textContent = updated.reviewed ? 'Қате қаралған деп белгіленді.' : 'Қате қайта қарау тізіміне қосылды.';
    } catch (error) {
      status.textContent = error.message;
      status.classList.add('is-error');
      button.disabled = false;
    }
  });
  footer.append(button);
  card.append(head, questionNo, prompt, answers, analysis, footer);
  return card;
}

function render() {
  const term = search.value.trim().toLocaleLowerCase('kk');
  const visible = mistakes.filter(item => matches(item, term));
  list.replaceChildren();
  if (visible.length) {
    visible.forEach(item => list.append(renderCard(item)));
    return;
  }
  if (!mistakes.length) {
    list.append(emptyState('Әзірге қате жоқ', 'Аяқталған тесттердегі қате жауаптар осында жиналады. Тест тапсырып, жауабыңызды талдаңыз.'));
  } else if (term) {
    list.append(emptyState('Сәйкес сұрақ табылмады', 'Іздеу сөзін өзгертіңіз немесе сүзгіні ауыстырыңыз.'));
  } else if (activeFilter === 'pending') {
    list.append(emptyState('Қайталау керек қате жоқ', 'Барлық қателеріңіз қаралды деп белгіленген. Жаңа тесттерден кейін бұл тізім жаңарады.'));
  } else {
    list.append(emptyState('Бұл сүзгіде қате жоқ', 'Қателердің басқа күйін көру үшін сүзгіні ауыстырыңыз.'));
  }
}

filters.forEach(button => button.addEventListener('click', () => {
  activeFilter = button.dataset.filter;
  filters.forEach(filter => {
    const selected = filter === button;
    filter.classList.toggle('is-active', selected);
    filter.setAttribute('aria-pressed', String(selected));
  });
  render();
}));
search.addEventListener('input', render);

async function loadMistakes() {
  list.setAttribute('aria-busy', 'true');
  try {
    const data = await api('/api/mistakes');
    mistakes = Array.isArray(data.items) ? data.items : [];
    updateSummary();
    status.textContent = '';
    status.classList.remove('is-error');
    render();
  } catch (error) {
    status.textContent = error.message;
    status.classList.add('is-error');
    list.replaceChildren(emptyState('Қателерді жүктеу мүмкін болмады', 'Интернет байланысын тексеріп, бетті қайта жүктеп көріңіз.'));
  } finally {
    list.setAttribute('aria-busy', 'false');
  }
}

loadMistakes();

(() => {
  'use strict';

  const catalogView = document.querySelector('#catalog-view');
  const readerView = document.querySelector('#reader-view');
  const filterBar = document.querySelector('#subject-filters');
  const grid = document.querySelector('#books-grid');
  const catalogStatus = document.querySelector('#catalog-status');
  const count = document.querySelector('#book-count');
  const backButton = document.querySelector('#back-to-books');
  const readerTitle = document.querySelector('#reader-title');
  const readerMeta = document.querySelector('#reader-meta');
  const readerAuthors = document.querySelector('#reader-authors');
  const readerStatus = document.querySelector('#reader-status');
  const pdfError = document.querySelector('#pdf-error');
  const pdfErrorText = document.querySelector('#pdf-error-text');
  const frameWrap = document.querySelector('#pdf-frame-wrap');
  const frame = document.querySelector('#pdf-frame');
  const openPdf = document.querySelector('#open-pdf');

  let books = [];
  let selectedSubject = 'all';
  let requestNumber = 0;

  function make(tag, text = '') {
    const element = document.createElement(tag);
    element.textContent = text;
    return element;
  }

  function login() {
    const next = window.location.pathname + window.location.search;
    window.location.replace('/infobyte-auth/login.html?next=' + encodeURIComponent(next));
  }

  async function api(path, options = {}) {
    const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store', ...options });
    if (response.status === 401) {
      login();
      throw new Error('Кіру бетіне бағытталып жатыр…');
    }
    return response;
  }

  function bookMeta(book) {
    return [book.publisher, book.year]
      .filter(value => value !== null && value !== undefined && String(value).trim() !== '')
      .join(' · ');
  }

  function makeFilter(label, value, active) {
    const button = make('button', label);
    button.type = 'button';
    button.className = 'subject-filter';
    button.dataset.subject = value;
    button.setAttribute('aria-pressed', String(active));
    button.addEventListener('click', () => {
      selectedSubject = value;
      filterBar.querySelectorAll('.subject-filter').forEach(filter => {
        const selected = filter.dataset.subject === value;
        filter.setAttribute('aria-pressed', String(selected));
      });
      renderBooks();
    });
    return button;
  }

  function renderFilters() {
    const subjects = [...new Set(books.map(book => book.subject).filter(subject => typeof subject === 'string' && subject.trim()))]
      .sort((a, b) => a.localeCompare(b, 'kk'));
    if (selectedSubject !== 'all' && !subjects.includes(selectedSubject)) selectedSubject = 'all';
    filterBar.replaceChildren(makeFilter('Барлығы', 'all', selectedSubject === 'all'));
    subjects.forEach(subject => filterBar.append(makeFilter(subject, subject, selectedSubject === subject)));
  }

  function addMetaRow(container, label, value) {
    if (value === null || value === undefined || String(value).trim() === '') return;
    const row = make('span');
    const strong = make('strong', label + ': ');
    row.append(strong, document.createTextNode(String(value)));
    container.append(row);
  }

  function createBookCard(book) {
    const card = make('button');
    card.type = 'button';
    card.className = 'book-card' + (book.available ? '' : ' is-unavailable');
    card.setAttribute('aria-label', `${book.title}${book.grade ? ', ' + book.grade : ''}. ${book.available ? 'Кітапты ашу' : 'PDF файлы жоқ'}`);

    const cover = make('span');
    cover.className = 'book-cover';
    cover.setAttribute('aria-hidden', 'true');
    const coverTitle = make('span', book.title);
    coverTitle.className = 'book-cover-title';
    cover.append(coverTitle);

    const body = make('span');
    body.className = 'book-card-body';
    if (book.grade) {
      const grade = make('span', book.grade);
      grade.className = 'book-grade';
      body.append(grade);
    }
    const title = make('span', book.title);
    title.className = 'book-title';
    body.append(title);
    if (book.subject) {
      const subject = make('span', book.subject);
      subject.className = 'book-subject';
      body.append(subject);
    }
    const meta = make('span');
    meta.className = 'book-meta';
    addMetaRow(meta, 'Баспа', book.publisher);
    addMetaRow(meta, 'Жылы', book.year);
    const authors = Array.isArray(book.authors)
      ? book.authors.filter(name => typeof name === 'string' && name.trim()).join(', ')
      : '';
    addMetaRow(meta, 'Авторлар', authors);
    if (meta.childElementCount) body.append(meta);
    if (!book.available) {
      const warning = make('span', 'PDF файлы табылмады');
      warning.className = 'availability';
      body.append(warning);
    }

    card.append(cover, body);
    card.addEventListener('click', () => openBook(book, true));
    return card;
  }

  function renderBooks() {
    const visibleBooks = selectedSubject === 'all'
      ? books
      : books.filter(book => book.subject === selectedSubject);
    grid.replaceChildren();
    count.textContent = `${visibleBooks.length} кітап`;

    if (!books.length) {
      const empty = make('div');
      empty.className = 'empty-catalog';
      const icon = make('span', '▤');
      icon.className = 'empty-catalog-icon';
      const heading = make('h3', 'Әзірге кітап қосылмаған');
      const copy = make('p', 'Кітап қосу үшін PDF файлын books/ қалтасына, ал оның мәліметтерін books/catalog.json файлына енгізіңіз. Каталог бет жаңартылғанда қайта оқылады.');
      empty.append(icon, heading, copy);
      grid.append(empty);
      return;
    }

    if (!visibleBooks.length) {
      const empty = make('div');
      empty.className = 'empty-catalog';
      const icon = make('span', '⌕');
      icon.className = 'empty-catalog-icon';
      empty.append(icon, make('h3', 'Бұл пәнде кітап жоқ'), make('p', 'Басқа пәнді таңдаңыз.'));
      grid.append(empty);
      return;
    }

    visibleBooks.forEach(book => grid.append(createBookCard(book)));
  }

  function setReaderError(message) {
    readerStatus.textContent = '';
    readerStatus.classList.remove('is-error');
    frameWrap.hidden = true;
    frame.removeAttribute('src');
    openPdf.hidden = true;
    pdfErrorText.textContent = message;
    pdfError.hidden = false;
  }

  async function openBook(book, pushHistory) {
    const currentRequest = ++requestNumber;
    const url = `/api/reading/books/${encodeURIComponent(book.id)}/pdf`;
    catalogView.hidden = true;
    readerView.hidden = false;
    readerTitle.textContent = book.title;
    const details = [book.subject, book.grade, bookMeta(book)]
      .filter(value => value !== null && value !== undefined && String(value).trim());
    readerMeta.textContent = details.join(' · ');
    readerAuthors.textContent = Array.isArray(book.authors) && book.authors.length
      ? `Авторлар: ${book.authors.join(', ')}`
      : '';
    readerStatus.classList.remove('is-error');
    readerStatus.textContent = '';
    pdfError.hidden = true;
    frameWrap.hidden = true;
    frame.removeAttribute('src');
    openPdf.hidden = true;
    openPdf.href = url;

    if (pushHistory) {
      const next = new URL(window.location.href);
      next.searchParams.set('book', book.id);
      window.history.pushState({ bookId: book.id }, '', next);
    }
    document.title = `${book.title} · Кітап оқу · InfoByte`;

    if (!book.available) {
      setReaderError('Каталогта бұл басылым тіркелген, бірақ books/ қалтасындағы PDF файлы табылмады. Файлды қосқан соң бетті жаңартып көріңіз.');
      return;
    }

    readerStatus.textContent = 'PDF тексеріліп жатыр…';
    try {
      const response = await api(url, { method: 'HEAD' });
      if (currentRequest !== requestNumber) return;
      if (!response.ok) {
        setReaderError(response.status === 404
          ? 'Бұл кітаптың PDF файлы серверден табылмады. Файлды books/ қалтасына қосып, бетті жаңартыңыз.'
          : 'PDF файлын тексеру сәтсіз аяқталды. Біраздан кейін қайта көріңіз.');
        return;
      }
      readerStatus.textContent = '';
      frame.title = `${book.title} — PDF оқу аймағы`;
      frame.addEventListener('error', () => {
        if (currentRequest === requestNumber) setReaderError('PDF оқу аймағын жүктеу мүмкін болмады. Жаңа бетте ашып көріңіз немесе кейінірек қайталаңыз.');
      }, { once: true });
      frame.src = url;
      frameWrap.hidden = false;
      openPdf.hidden = false;
    } catch (error) {
      if (currentRequest !== requestNumber) return;
      readerStatus.classList.add('is-error');
      readerStatus.textContent = error.message || 'Серверге қосылу мүмкін болмады.';
    }
  }

  function returnToCatalog() {
    requestNumber += 1;
    readerView.hidden = true;
    catalogView.hidden = false;
    document.title = 'Кітап оқу · InfoByte';
    frame.removeAttribute('src');
    const next = new URL(window.location.href);
    next.searchParams.delete('book');
    window.history.replaceState({ bookId: null }, '', next);
    renderFilters();
    renderBooks();
  }

  function syncFromUrl() {
    const bookId = new URLSearchParams(window.location.search).get('book');
    if (!bookId) {
      requestNumber += 1;
      readerView.hidden = true;
      catalogView.hidden = false;
      document.title = 'Кітап оқу · InfoByte';
      frame.removeAttribute('src');
      return;
    }
    const book = books.find(item => item.id === bookId);
    if (book) openBook(book, false);
    else {
      catalogView.hidden = false;
      readerView.hidden = true;
      catalogStatus.textContent = 'Сұралған кітап каталогтан табылмады.';
      catalogStatus.classList.add('is-error');
    }
  }

  async function loadCatalog() {
    grid.setAttribute('aria-busy', 'true');
    try {
      const response = await api('/api/reading/books');
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Кітап каталогын жүктеу мүмкін болмады.');
      books = Array.isArray(data) ? data : [];
      catalogStatus.textContent = '';
      catalogStatus.classList.remove('is-error');
      renderFilters();
      renderBooks();
      syncFromUrl();
    } catch (error) {
      books = [];
      renderFilters();
      renderBooks();
      catalogStatus.textContent = error.message || 'Кітап каталогын жүктеу мүмкін болмады.';
      catalogStatus.classList.add('is-error');
    } finally {
      grid.setAttribute('aria-busy', 'false');
    }
  }

  backButton.addEventListener('click', returnToCatalog);
  window.addEventListener('popstate', syncFromUrl);
  loadCatalog();
})();

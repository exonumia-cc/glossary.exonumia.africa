/* Bitcoin Glossary — multilingual dictionary view.
   Reads i18n/manifest.json (["en", "ki", ...]) plus one i18n/<lang>.json per
   language ({ category: [ {key, term, explanation, notes} ] }) and renders one
   column per language, with every term sharing a row. */

(function () {
  'use strict';

  /* Known language codes. Anything not listed still renders — it just falls back
     to the bare code — so new sheets can be added to the JSON with no code change. */
  var LANG_META = {
    en: { name: 'English',    native: 'English' },
    ki: { name: 'Kikuyu',     native: 'Gĩkũyũ' },
    sw: { name: 'Swahili',    native: 'Kiswahili' },
    so: { name: 'Somali',     native: 'Soomaali' },
    am: { name: 'Amharic',    native: 'አማርኛ' },
    ha: { name: 'Hausa',      native: 'Harshen Hausa' },
    yo: { name: 'Yoruba',     native: 'Yorùbá' },
    ig: { name: 'Igbo',       native: 'Asụsụ Igbo' },
    zu: { name: 'Zulu',       native: 'isiZulu' },
    xh: { name: 'Xhosa',      native: 'isiXhosa' },
    st: { name: 'Sesotho',    native: 'Sesotho' },
    tn: { name: 'Setswana',   native: 'Setswana' },
    sn: { name: 'Shona',      native: 'chiShona' },
    ln: { name: 'Lingala',    native: 'Lingála' },
    lg: { name: 'Luganda',    native: 'Luganda' },
    wo: { name: 'Wolof',      native: 'Wolof' },
    af: { name: 'Afrikaans',  native: 'Afrikaans' },
    fr: { name: 'French',     native: 'Français' },
    pt: { name: 'Portuguese', native: 'Português' },
    ar: { name: 'Arabic',     native: 'العربية', dir: 'rtl' }
  };

  /* Display names for the category slugs used in the i18n/*.json files. */
  var CATEGORY_LABELS = {
    'concepts':          'Bitcoin Concepts',
    'wallets':           'Wallets',
    'security':          'Security',
    'safety':            'Safety',
    'lightning-network': 'Lightning Network',
    'payments':          'Payments',
    'privacy':           'Privacy',
    'markets':           'Markets',
    'mobile-money':      'Mobile Money',
    'seedsigner':        'SeedSigner',
    'crypto-ecosystem':  'Crypto Ecosystem',
    'ui':                'Interface',
    'wallet-ui':         'Wallet Interface',
    'advanced-bitcoin':  'Advanced Bitcoin'
  };

  /* Persist which languages are switched OFF, not which are on: a language
     added to i18n/ later should then appear for returning visitors
     instead of staying hidden behind a stale preference. */
  var STORE_HIDDEN = 'exonumia-langs-hidden';
  var STORE_THEME = 'exonumia-theme';
  var STORE_SIDEBAR = 'exonumia-sidebar';

  var el = {
    glossary: document.getElementById('glossary'),
    colhead: document.getElementById('colhead'),
    loading: document.getElementById('loading'),
    empty: document.getElementById('empty'),
    search: document.getElementById('search'),
    chips: document.getElementById('lang-chips'),
    category: document.getElementById('category'),
    sidebar: document.getElementById('sidebar-list'),
    tally: document.getElementById('tally'),
    colophon: document.getElementById('colophon-meta'),
    toolbar: document.getElementById('toolbar'),
    reset: document.getElementById('reset'),
    theme: document.getElementById('theme-toggle'),
    sidebarToggle: document.getElementById('sidebar-toggle')
  };

  var model = null;
  var state = { query: '', langs: null, category: 'all' };

  /* ------------------------------------------------------------ text utils */

  /* Fold to lowercase ASCII-ish for search, keeping a map from each folded
     character back to its index in the original string so matches can be
     highlighted in the untouched text. Lets "muthiu" find "mũthĩũ". */
  function fold(str) {
    var out = '', map = [], i, j, ch;
    for (i = 0; i < str.length; i++) {
      ch = str[i].normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
      for (j = 0; j < ch.length; j++) { out += ch[j]; map.push(i); }
    }
    map.push(str.length);
    return { text: out, map: map };
  }

  function foldText(str) { return fold(str).text; }

  function highlightInto(node, text, tokens) {
    if (!text) { node.textContent = ''; return; }
    if (!tokens.length) { node.textContent = text; return; }

    var folded = fold(text), ranges = [], i, at, from, t;
    for (i = 0; i < tokens.length; i++) {
      t = tokens[i];
      from = 0;
      while ((at = folded.text.indexOf(t, from)) !== -1) {
        ranges.push([folded.map[at], folded.map[at + t.length]]);
        from = at + t.length;
      }
    }
    if (!ranges.length) { node.textContent = text; return; }

    ranges.sort(function (a, b) { return a[0] - b[0]; });
    var merged = [];
    for (i = 0; i < ranges.length; i++) {
      var last = merged[merged.length - 1];
      if (last && ranges[i][0] <= last[1]) last[1] = Math.max(last[1], ranges[i][1]);
      else merged.push([ranges[i][0], ranges[i][1]]);
    }

    var frag = document.createDocumentFragment(), cursor = 0;
    for (i = 0; i < merged.length; i++) {
      if (merged[i][0] > cursor) {
        frag.appendChild(document.createTextNode(text.slice(cursor, merged[i][0])));
      }
      var mark = document.createElement('mark');
      mark.textContent = text.slice(merged[i][0], merged[i][1]);
      frag.appendChild(mark);
      cursor = merged[i][1];
    }
    if (cursor < text.length) frag.appendChild(document.createTextNode(text.slice(cursor)));

    node.textContent = '';
    node.appendChild(frag);
  }

  function langMeta(code) {
    return LANG_META[code] || { name: code.toUpperCase(), native: '' };
  }

  function categoryLabel(slug) {
    if (CATEGORY_LABELS[slug]) return CATEGORY_LABELS[slug];
    return slug.split('-').map(function (w) {
      return w.charAt(0).toUpperCase() + w.slice(1);
    }).join(' ');
  }

  /* ------------------------------------------------------------ data model */

  function buildModel(data) {
    var langCodes = Object.keys(data);
    var catOrder = [], seenCat = {};

    langCodes.forEach(function (lang) {
      Object.keys(data[lang]).forEach(function (cat) {
        if (!seenCat[cat]) { seenCat[cat] = true; catOrder.push(cat); }
      });
    });

    var categories = catOrder.map(function (cat) {
      var lookup = {}, keyOrder = [], seenKey = {};

      langCodes.forEach(function (lang) {
        lookup[lang] = {};
        (data[lang][cat] || []).forEach(function (entry) {
          lookup[lang][entry.key] = entry;
          if (!seenKey[entry.key]) { seenKey[entry.key] = true; keyOrder.push(entry.key); }
        });
      });

      var entries = keyOrder.map(function (key) {
        var byLang = {}, search = {};
        langCodes.forEach(function (lang) {
          var entry = lookup[lang][key] || null;
          byLang[lang] = entry;
          search[lang] = foldText(entry
            ? [key, entry.term, entry.explanation, entry.notes].join(' ')
            : key);
        });
        return { key: key, category: cat, byLang: byLang, search: search };
      });

      return { key: cat, label: categoryLabel(cat), entries: entries };
    });

    return { langCodes: langCodes, categories: categories };
  }

  function activeLangs() {
    return model.langCodes.filter(function (code) { return state.langs.has(code); });
  }

  function matches(entry, tokens, langs) {
    if (!tokens.length) return true;
    for (var i = 0; i < tokens.length; i++) {
      var hit = false;
      for (var j = 0; j < langs.length; j++) {
        if (entry.search[langs[j]].indexOf(tokens[i]) !== -1) { hit = true; break; }
      }
      if (!hit) return false;
    }
    return true;
  }

  /* --------------------------------------------------------------- render */

  function renderColumnHead(langs) {
    el.colhead.textContent = '';
    langs.forEach(function (code) {
      var meta = langMeta(code);
      var cell = document.createElement('div');
      cell.className = 'colhead__cell';

      var name = document.createElement('div');
      name.className = 'colhead__name';
      name.textContent = meta.native || meta.name;
      cell.appendChild(name);

      var sub = document.createElement('div');
      sub.className = 'colhead__meta';
      sub.textContent = meta.native && meta.native !== meta.name
        ? meta.name + ' · ' + code
        : code;
      cell.appendChild(sub);

      el.colhead.appendChild(cell);
    });
  }

  function renderCell(entry, code, tokens) {
    var meta = langMeta(code);
    var cell = document.createElement('div');
    cell.className = 'cell';
    cell.lang = code;
    if (meta.dir) cell.dir = meta.dir;

    var label = document.createElement('div');
    label.className = 'cell__lang';
    label.textContent = meta.native || meta.name;
    cell.appendChild(label);

    var term = document.createElement('div');
    term.className = 'cell__term';

    if (!entry) {
      cell.className += ' cell--empty';
      term.textContent = '— not yet translated';
      cell.appendChild(term);
      return cell;
    }

    highlightInto(term, entry.term, tokens);
    cell.appendChild(term);

    if (entry.explanation) {
      var exp = document.createElement('p');
      exp.className = 'cell__explanation';
      highlightInto(exp, entry.explanation, tokens);
      cell.appendChild(exp);
    }

    if (entry.notes) {
      var note = document.createElement('p');
      note.className = 'cell__note';
      var tag = document.createElement('b');
      tag.textContent = 'Note';
      note.appendChild(tag);
      note.appendChild(document.createTextNode(' '));
      var body = document.createElement('span');
      highlightInto(body, entry.notes, tokens);
      note.appendChild(body);
      cell.appendChild(note);
    }

    return cell;
  }

  function renderEntry(entry, langs, tokens) {
    var row = document.createElement('div');
    row.className = 'entry';
    row.id = 'entry-' + entry.category + '-' + entry.key;

    var anchor = document.createElement('a');
    anchor.className = 'entry__anchor';
    anchor.href = '#' + entry.category + '/' + entry.key;
    anchor.textContent = '§';
    anchor.title = 'Link to “' + entry.key + '”';
    anchor.setAttribute('aria-label', 'Link to this entry');
    row.appendChild(anchor);

    langs.forEach(function (code) {
      row.appendChild(renderCell(entry.byLang[code], code, tokens));
    });

    return row;
  }

  function render() {
    var langs = activeLangs();
    var tokens = state.query ? foldText(state.query).split(/\s+/).filter(Boolean) : [];

    document.documentElement.style.setProperty('--cols', langs.length);
    renderColumnHead(langs);

    var frag = document.createDocumentFragment();
    var shown = 0, total = 0, counts = {};

    model.categories.forEach(function (category) {
      var hits = category.entries.filter(function (entry) {
        return matches(entry, tokens, langs);
      });
      counts[category.key] = hits.length;
      total += category.entries.length;

      if (state.category !== 'all' && state.category !== category.key) return;
      if (!hits.length) return;
      shown += hits.length;

      var section = document.createElement('section');
      section.className = 'section';
      section.id = 'cat-' + category.key;

      var head = document.createElement('div');
      head.className = 'section__head';

      var title = document.createElement('h2');
      title.textContent = category.label;
      head.appendChild(title);

      var rule = document.createElement('span');
      rule.className = 'section__rule';
      head.appendChild(rule);

      var count = document.createElement('span');
      count.className = 'section__count';
      count.textContent = hits.length + (hits.length === 1 ? ' term' : ' terms');
      head.appendChild(count);

      section.appendChild(head);
      hits.forEach(function (entry) {
        section.appendChild(renderEntry(entry, langs, tokens));
      });
      frag.appendChild(section);
    });

    el.glossary.textContent = '';
    el.glossary.appendChild(frag);
    el.empty.hidden = shown > 0;
    el.colhead.hidden = shown === 0;

    renderSidebar(counts);
    updateCategoryOptions(counts);

    var filtered = state.query || state.category !== 'all';
    el.tally.innerHTML = '';
    el.tally.appendChild(document.createTextNode(
      filtered
        ? 'Showing ' + shown + ' of ' + total + ' terms'
        : total + ' terms · ' + model.categories.length + ' categories · ' +
          langs.length + ' of ' + model.langCodes.length + ' languages'
    ));
  }

  function renderSidebar(counts) {
    el.sidebar.textContent = '';

    var rows = [{ key: 'all', label: 'All categories', count: null }].concat(
      model.categories.map(function (c) {
        return { key: c.key, label: c.label, count: counts[c.key] };
      })
    );

    rows.forEach(function (row) {
      var li = document.createElement('li');
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('aria-current', state.category === row.key ? 'true' : 'false');
      if (row.count === 0) btn.disabled = true;

      var name = document.createElement('span');
      name.textContent = row.label;
      btn.appendChild(name);

      var count = document.createElement('span');
      count.className = 'sidebar__count';
      count.textContent = row.count === null
        ? model.categories.reduce(function (sum, c) { return sum + counts[c.key]; }, 0)
        : row.count;
      btn.appendChild(count);

      btn.addEventListener('click', function () {
        state.category = row.key;
        render();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });

      li.appendChild(btn);
      el.sidebar.appendChild(li);
    });
  }

  function updateCategoryOptions(counts) {
    var wanted = ['all'].concat(model.categories.map(function (c) { return c.key; }));
    if (el.category.options.length !== wanted.length) {
      el.category.textContent = '';
      wanted.forEach(function (key) {
        var opt = document.createElement('option');
        opt.value = key;
        el.category.appendChild(opt);
      });
    }
    Array.prototype.forEach.call(el.category.options, function (opt, i) {
      if (i === 0) { opt.textContent = 'All categories'; return; }
      var category = model.categories[i - 1];
      opt.textContent = category.label + ' (' + counts[category.key] + ')';
    });
    el.category.value = state.category;
  }

  function renderChips() {
    el.chips.textContent = '';
    model.langCodes.forEach(function (code) {
      var meta = langMeta(code);
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'chip';
      chip.setAttribute('aria-pressed', state.langs.has(code) ? 'true' : 'false');

      var name = document.createElement('span');
      name.textContent = meta.native || meta.name;
      chip.appendChild(name);

      var tag = document.createElement('span');
      tag.className = 'chip__code';
      tag.textContent = code;
      chip.appendChild(tag);

      chip.addEventListener('click', function () {
        if (state.langs.has(code)) {
          if (state.langs.size === 1) return;  // always keep one column visible
          state.langs.delete(code);
        } else {
          state.langs.add(code);
        }
        try {
          localStorage.setItem(STORE_HIDDEN, model.langCodes.filter(function (c) {
            return !state.langs.has(c);
          }).join(','));
        } catch (e) {}
        chip.setAttribute('aria-pressed', state.langs.has(code) ? 'true' : 'false');
        render();
      });

      el.chips.appendChild(chip);
    });
  }

  /* ------------------------------------------------------------- deep links */

  function applyHash() {
    var raw = window.location.hash.replace(/^#/, '');
    if (!raw || raw.indexOf('/') === -1) return;

    var parts = raw.split('/');
    var id = 'entry-' + parts[0] + '-' + parts.slice(1).join('/');

    if (!document.getElementById(id)) {
      state.query = '';
      el.search.value = '';
      state.category = parts[0];
      render();
    }

    var target = document.getElementById(id);
    if (!target) return;

    Array.prototype.forEach.call(
      document.querySelectorAll('.entry.is-linked'),
      function (n) { n.classList.remove('is-linked'); }
    );
    target.classList.add('is-linked');
    target.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }

  /* ------------------------------------------------------------------ wire */

  function debounce(fn, ms) {
    var timer;
    return function () {
      clearTimeout(timer);
      timer = setTimeout(fn, ms);
    };
  }

  function setSidebar(hidden, persist) {
    var root = document.documentElement;
    var label = (hidden ? 'Show' : 'Hide') + ' the category list';

    if (hidden) root.dataset.sidebar = 'hidden';
    else delete root.dataset.sidebar;

    el.sidebarToggle.setAttribute('aria-expanded', hidden ? 'false' : 'true');
    el.sidebarToggle.title = label;
    el.sidebarToggle.querySelector('.sr-only').textContent = label;

    if (persist) {
      try { localStorage.setItem(STORE_SIDEBAR, hidden ? 'hidden' : 'shown'); } catch (e) {}
    }
  }

  function wire() {
    // The inline head script already applied the stored state; match the button to it.
    setSidebar(document.documentElement.dataset.sidebar === 'hidden', false);
    el.sidebarToggle.addEventListener('click', function () {
      setSidebar(document.documentElement.dataset.sidebar !== 'hidden', true);
    });

    el.search.addEventListener('input', debounce(function () {
      state.query = el.search.value.trim();
      render();
    }, 120));

    el.category.addEventListener('change', function () {
      state.category = el.category.value;
      render();
    });

    el.reset.addEventListener('click', function () {
      state.query = '';
      state.category = 'all';
      el.search.value = '';
      render();
      el.search.focus();
    });

    el.theme.addEventListener('click', function () {
      var next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      el.theme.setAttribute('aria-label',
        next === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
      try { localStorage.setItem(STORE_THEME, next); } catch (e) {}
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === '/' && document.activeElement !== el.search) {
        event.preventDefault();
        el.search.focus();
        el.search.select();
      } else if (event.key === 'Escape' && document.activeElement === el.search) {
        el.search.value = '';
        state.query = '';
        render();
      }
    });

    window.addEventListener('hashchange', applyHash);

    if (window.ResizeObserver) {
      new ResizeObserver(function () {
        document.documentElement.style.setProperty(
          '--toolbar-h', el.toolbar.offsetHeight + 'px');
      }).observe(el.toolbar);
    } else {
      document.documentElement.style.setProperty(
        '--toolbar-h', el.toolbar.offsetHeight + 'px');
    }
  }

  function restoreLangs(codes) {
    var hidden = '';
    try { hidden = localStorage.getItem(STORE_HIDDEN) || ''; } catch (e) {}
    var off = hidden.split(',');
    var shown = codes.filter(function (code) { return off.indexOf(code) === -1; });
    return new Set(shown.length ? shown : codes);
  }

  function showError(message) {
    el.loading.hidden = true;
    var box = document.createElement('div');
    box.className = 'error';

    var title = document.createElement('h2');
    title.textContent = 'Could not load the glossary data';
    box.appendChild(title);

    var body = document.createElement('p');
    body.textContent = message + ' Browsers block file reads on file:// URLs, ' +
      'so this page needs to be served over HTTP. From this folder, run:';
    box.appendChild(body);

    var pre = document.createElement('pre');
    pre.textContent = 'python3 -m http.server 8000\n# then open http://localhost:8000';
    box.appendChild(pre);

    el.glossary.appendChild(box);
  }

  /* Fetch i18n/manifest.json, then every language file it lists, and rebuild
     the { lang: { category: [entry] } } shape buildModel expects. */
  function loadGlossary() {
    return fetch('i18n/manifest.json')
      .then(function (response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.json();
      })
      .then(function (codes) {
        return Promise.all(codes.map(function (code) {
          return fetch('i18n/' + code + '.json').then(function (response) {
            if (!response.ok) throw new Error('HTTP ' + response.status + ' for i18n/' + code + '.json');
            return response.json();
          }).then(function (langData) {
            return { code: code, data: langData };
          });
        }));
      })
      .then(function (parts) {
        var data = {};
        parts.forEach(function (part) { data[part.code] = part.data; });
        return data;
      });
  }

  loadGlossary()
    .then(function (data) {
      model = buildModel(data);
      state.langs = restoreLangs(model.langCodes);
      state.query = el.search.value.trim();  // browsers restore field values on reload

      el.loading.hidden = true;
      renderChips();
      wire();
      render();
      applyHash();

      var total = model.categories.reduce(function (sum, c) {
        return sum + c.entries.length;
      }, 0);
      el.colophon.textContent = total + ' entries · ' + model.categories.length +
        ' categories · ' + model.langCodes.length + ' languages (' +
        model.langCodes.join(', ') + ')';
    })
    .catch(function (error) {
      showError(error.message + '.');
    });
})();

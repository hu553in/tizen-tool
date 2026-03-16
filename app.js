var HISTORY_KEY = 'multitwitch_tv_history';
var HISTORY_LIMIT = 4;

function getSanitizedChannels(comboString) {
  if (!comboString) return [];

  return comboString
    .trim()
    .split(/[,\s]+/)
    .filter(Boolean)
    .map(function (name) {
      return name.replace(/[^a-zA-Z0-9_]/g, '');
    })
    .filter(Boolean);
}

function normalizeComboString(comboString) {
  var channels = getSanitizedChannels(comboString);
  if (!channels.length) return null;
  return channels.join(' ');
}

function sanitizeHistoryList(list) {
  if (!Array.isArray(list)) return [];

  var seen = Object.create(null);

  return list
    .map(normalizeComboString)
    .filter(function (item) {
      if (!item || seen[item]) {
        return false;
      }

      seen[item] = true;
      return true;
    })
    .slice(0, HISTORY_LIMIT);
}

function loadHistory() {
  try {
    var raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    var parsed = JSON.parse(raw);
    return sanitizeHistoryList(parsed);
  } catch (e) {
    console.log('Failed to load history:', e);
    return [];
  }
}

function saveHistory(list) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(sanitizeHistoryList(list)));
  } catch (e) {
    console.log('Failed to save history:', e);
  }
}

function addHistoryItem(comboString) {
  var normalizedCombo = normalizeComboString(comboString);
  if (!normalizedCombo) return;

  var history = loadHistory().filter(function (item) {
    return item !== normalizedCombo;
  });

  history.unshift(normalizedCombo);
  saveHistory(history);
  renderHistory();
}

function renderHistory() {
  var history = loadHistory();
  var list = document.getElementById('history-list');
  var empty = document.getElementById('history-empty');

  list.innerHTML = '';

  if (!history.length) {
    empty.classList.remove('hidden');
    return;
  }

  empty.classList.add('hidden');

  history.forEach(function (combo) {
    var li = document.createElement('li');
    var btn = document.createElement('button');

    btn.className = 'history-item-btn';
    btn.type = 'button';
    btn.textContent = combo;
    btn.addEventListener('click', function () {
      useHistoryCombo(combo);
    });

    li.appendChild(btn);
    list.appendChild(li);
  });
}

function buildMultiTwitchUrlFromComboString(comboString) {
  var sanitized = getSanitizedChannels(comboString);

  if (!sanitized.length) {
    return null;
  }

  return 'https://www.multitwitch.tv/' + sanitized.map(encodeURIComponent).join('/');
}

function exitApplication() {
  try {
    tizen.application.getCurrentApplication().exit();
  } catch (err) {
    console.log('Exit failed:', err);
  }
}

function openMultiTwitchFromInput() {
  var input = document.getElementById('channel-input');
  var comboString = normalizeComboString(input.value || '');
  if (!comboString) return;

  var url = buildMultiTwitchUrlFromComboString(comboString);
  if (!url) return;

  input.value = comboString;
  addHistoryItem(comboString);
  window.location.href = url;
}

function useHistoryCombo(comboString) {
  var input = document.getElementById('channel-input');
  input.value = comboString;
  openMultiTwitchFromInput();
}

function onKeyDown(e) {
  if (e.keyCode === 10009) {
    exitApplication();
  }

  if (e.keyCode === 13) {
    openMultiTwitchFromInput();
  }
}

function onTizenHwKey(e) {
  if (e.keyName === 'back') {
    if (e.preventDefault) {
      e.preventDefault();
    }
    exitApplication();
  }
}

window.onload = function () {
  var input = document.getElementById('channel-input');
  var button = document.getElementById('watch-btn');

  renderHistory();

  try {
    input.focus();
  } catch (e) {
    console.log('Focus failed:', e);
  }

  button.addEventListener('click', openMultiTwitchFromInput);
  document.addEventListener('keydown', onKeyDown);
  window.addEventListener('tizenhwkey', onTizenHwKey);
};

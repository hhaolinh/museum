(() => {
  const normalize = text => text.normalize('NFKD').replace(/\p{M}/gu, '').toLocaleLowerCase().trim();

  class SearchSelect {
    constructor(select, load = null) {
      this.select = select;
      this.load = load;
      this.options = [...select.options].map(option => ({id: option.value, label: option.textContent}));
      this.results = [];
      this.active = -1;
      this.version = 0;
      const id = select.id;
      select.removeAttribute('id');
      select.hidden = true;
      this.wrapper = document.createElement('div');
      this.wrapper.className = 'search-select';
      this.input = document.createElement('input');
      this.input.id = id;
      this.input.type = 'text';
      this.input.autocomplete = 'off';
      this.input.placeholder = '搜索或选择';
      this.input.setAttribute('role', 'combobox');
      this.input.setAttribute('aria-autocomplete', 'list');
      this.input.setAttribute('aria-expanded', 'false');
      this.input.setAttribute('aria-controls', `${id}-options`);
      this.clear = document.createElement('button');
      this.clear.type = 'button';
      this.clear.className = 'search-select-clear';
      this.clear.textContent = '×';
      const label = document.querySelector(`label[for="${id}"]`).textContent;
      this.clear.setAttribute('aria-label', `清空${label}`);
      this.popup = document.createElement('div');
      this.popup.className = 'search-select-popup';
      this.popup.hidden = true;
      this.list = document.createElement('div');
      this.list.id = `${id}-options`;
      this.list.setAttribute('role', 'listbox');
      this.list.setAttribute('aria-label', label);
      this.status = document.createElement('div');
      this.status.className = 'search-select-status';
      this.status.setAttribute('role', 'status');
      this.popup.append(this.list, this.status);
      this.wrapper.append(this.input, this.clear, this.popup);
      select.after(this.wrapper);
      this.sync();
      this.setDisabled(select.disabled);
      this.input.addEventListener('focus', () => {
        this.input.select();
        this.search('');
      });
      this.input.addEventListener('click', () => {
        if (this.popup.hidden) { this.input.select(); this.search(''); }
      });
      this.input.addEventListener('input', () => this.search(this.input.value));
      this.input.addEventListener('blur', () => { this.close(); this.sync(); });
      this.popup.addEventListener('pointerdown', event => event.preventDefault());
      this.clear.addEventListener('pointerdown', event => event.preventDefault());
      this.clear.addEventListener('click', () => { this.choose({id: '', label: ''}); this.input.focus(); });
      this.input.addEventListener('keydown', event => {
        if (event.key === 'Escape') { event.preventDefault(); this.close(); this.sync(); }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          if (this.popup.hidden) { this.search(''); return; }
          if (!this.results.length) return;
          this.active = (this.active + (event.key === 'ArrowDown' ? 1 : -1) + this.results.length) % this.results.length;
          this.highlight();
        }
        if (event.key === 'Enter' && !this.popup.hidden) {
          event.preventDefault();
          if (this.active >= 0 && this.results[this.active]) this.choose(this.results[this.active]);
        }
        if (event.key === 'Tab') { this.close(); this.sync(); }
      });
      select.addEventListener('change', () => this.sync());
    }
    sync() {
      this.input.value = this.select.value ? this.select.selectedOptions[0]?.textContent || '' : '';
      this.clear.hidden = !this.select.value || this.input.disabled;
    }
    close() {
      this.version++;
      clearTimeout(this.timer);
      this.controller?.abort();
      this.popup.hidden = true;
      this.input.setAttribute('aria-expanded', 'false');
      this.input.removeAttribute('aria-activedescendant');
    }
    setDisabled(disabled) {
      this.select.disabled = disabled;
      this.input.disabled = disabled;
      this.wrapper.classList.toggle('is-disabled', disabled);
      if (disabled) this.close();
      this.sync();
    }
    reset() {
      const changed = this.select.value !== '';
      this.select.value = '';
      this.close();
      this.sync();
      if (changed) this.select.dispatchEvent(new Event('change', {bubbles:true}));
    }
    choose(option) {
      if (option.id && ![...this.select.options].some(item => item.value === option.id)) {
        this.select.add(new Option(option.label, option.id));
      }
      const changed = this.select.value !== option.id;
      this.select.value = option.id;
      this.close();
      this.sync();
      if (changed) this.select.dispatchEvent(new Event('change', {bubbles:true}));
    }
    async search(query) {
      this.query = query;
      if (this.input.disabled) return;
      const version = ++this.version;
      clearTimeout(this.timer);
      this.controller?.abort();
      this.popup.hidden = false;
      const rect = this.wrapper.getBoundingClientRect();
      this.popup.classList.toggle('opens-up', innerHeight - rect.bottom < 280 && rect.top > innerHeight - rect.bottom);
      this.input.setAttribute('aria-expanded', 'true');
      this.input.removeAttribute('aria-activedescendant');
      this.active = -1;
      this.results = [];
      this.list.replaceChildren();
      if (!this.load) {
        const key = normalize(query);
        const matches = this.options.filter(option => !option.id || normalize(option.label).includes(key) || normalize(option.id) === key);
        if (key) matches.sort((a,b) => Number(normalize(b.id) === key) - Number(normalize(a.id) === key));
        this.render(matches, matches.some(option => option.id) ? '' : '没有匹配选项');
        return;
      }
      this.status.textContent = '正在查找…';
      this.timer = setTimeout(async () => {
        this.controller = new AbortController();
        try {
          const data = await this.load(query, this.controller.signal);
          if (this.version !== version) return;
          this.render([{id:'', label:'暂不填写'}, ...data.cities], data.total > 100 ? '继续输入以缩小范围' : !data.total ? '未找到城市，试试其他名称' : '');
        } catch (error) {
          if (this.version === version && error.name !== 'AbortError') this.status.textContent = '加载失败，重新输入以重试';
        }
      }, 150);
    }
    render(options, message) {
      this.results = options;
      this.status.textContent = message;
      options.forEach((option, index) => {
        const row = document.createElement('div');
        row.id = `${this.list.id}-${index}`;
        row.className = 'search-select-option';
        row.setAttribute('role', 'option');
        row.setAttribute('aria-selected', String(option.id === this.select.value));
        row.textContent = option.label;
        row.addEventListener('click', () => this.choose(option));
        this.list.append(row);
      });
      this.active = this.query ? options.findIndex(option => option.id) : -1;
      if (this.active >= 0) this.highlight();
    }
    highlight() {
      [...this.list.children].forEach((row, index) => row.classList.toggle('is-active', index === this.active));
      const row = this.list.children[this.active];
      if (row) {
        this.input.setAttribute('aria-activedescendant', row.id);
        if (row.offsetTop < this.popup.scrollTop) this.popup.scrollTop = row.offsetTop;
        else if (row.offsetTop + row.offsetHeight > this.popup.scrollTop + this.popup.clientHeight) this.popup.scrollTop = row.offsetTop + row.offsetHeight - this.popup.clientHeight;
      }
    }
  }

  const country = document.querySelector('#country-code');
  if (!country) return;
  const city = document.querySelector('#place-id');
  const currency = document.querySelector('#currency-code');
  const amount = document.querySelector('#price-amount');
  const countryWidget = new SearchSelect(country);
  const cityWidget = new SearchSelect(city, async (query, signal) => {
    const response = await fetch(`/api/places?${new URLSearchParams({country:country.value, q:query})}`, {signal});
    if (!response.ok) throw new Error('加载失败');
    return response.json();
  });
  const currencyWidget = new SearchSelect(currency);
  const localCurrencies = JSON.parse(document.querySelector('#country-currencies').textContent);
  const localCurrency = document.createElement('button');
  localCurrency.type = 'button';
  localCurrency.className = 'local-currency';
  currencyWidget.wrapper.after(localCurrency);
  function updateLocalCurrency() {
    const code = localCurrencies[country.value];
    localCurrency.hidden = !code || ![...currency.options].some(option => option.value === code);
    localCurrency.textContent = code ? `使用当地货币 ${code}` : '';
    localCurrency.disabled = amount.value === '' || currency.value === code;
  }
  localCurrency.addEventListener('click', () => {
    const code = localCurrencies[country.value];
    const option = [...currency.options].find(option => option.value === code);
    if (option && amount.value !== '') currencyWidget.choose({id: code, label: option.textContent});
  });
  country.addEventListener('change', updateLocalCurrency);

  country.addEventListener('change', () => {
    cityWidget.reset();
    cityWidget.setDisabled(!country.value);
  });
  cityWidget.setDisabled(!country.value);
  function updateAmount() {
    const enabled = amount.value !== '';
    if (!enabled) currencyWidget.reset();
    currencyWidget.setDisabled(!enabled);
    // SearchSelect supplies the visible validity target; the hidden select only submits a code.
    currencyWidget.input.required = enabled;
    currencyWidget.input.setCustomValidity(enabled && !currency.value ? '请选择币种' : '');
    const digits = Number(currency.selectedOptions[0]?.dataset.digits ?? 4);
    amount.step = String(10 ** -digits);
    updateLocalCurrency();
  }
  amount.addEventListener('input', updateAmount);
  currency.addEventListener('change', updateAmount);
  updateAmount();

  const year = document.querySelector('#date-year');
  const month = document.querySelector('#date-month');
  const day = document.querySelector('#date-day');
  function updateDate() {
    const hasYear = /^[0-9]{4}$/.test(year.value) && year.validity.valid;
    month.disabled = !hasYear;
    const today = new Date();
    for (const option of month.options) {
      option.disabled = hasYear && Number(year.value) === today.getFullYear() && Number(option.value) > today.getMonth() + 1;
    }
    if (!hasYear || month.selectedOptions[0]?.disabled) month.value = '';
    day.disabled = !hasYear || !month.value;
    const selectedDay = day.value;
    const count = !day.disabled ? new Date(Number(year.value), Number(month.value), 0).getDate() : 0;
    day.replaceChildren(new Option('—',''));
    for (let value=1; value<=count; value++) {
      const option = new Option(String(value),String(value));
      option.disabled = Number(year.value) === today.getFullYear() && Number(month.value) === today.getMonth()+1 && value > today.getDate();
      day.add(option);
    }
    day.value = selectedDay && Number(selectedDay)<=count ? selectedDay : '';
    if (day.selectedOptions[0]?.disabled) day.value = '';
  }
  year.addEventListener('input', updateDate);
  month.addEventListener('change', updateDate);
  updateDate();
})();

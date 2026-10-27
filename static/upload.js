(() => {
  const field = document.querySelector('[data-photo-upload]');
  if (!field) return;
  const input = field.querySelector('input[type="file"]');
  const preview = field.querySelector('.photo-preview');
  const image = preview.querySelector('img');
  const error = field.querySelector('.photo-error');
  const prompt = field.querySelector('.photo-prompt');
  const action = field.querySelector('.photo-action');
  let previewUrl;

  function clear() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    input.value = '';
    image.removeAttribute('src');
    preview.hidden = true;
    field.classList.remove('has-photo');
    prompt.textContent = '为它留一张照片';
    action.firstChild.textContent = '选择本地图片 ';
    error.hidden = true;
  }
  function reject(message) {
    clear();
    error.textContent = message;
    error.hidden = false;
  }
  input.addEventListener('change', () => {
    const file = input.files[0];
    if (!file) return;
    if (file.size >= 10 * 1024 * 1024) {
      reject('照片太大了，请选择小于 10 MB 的图片。');
      return;
    }
    if (file.type && !['image/jpeg', 'image/png', 'image/webp', 'image/gif'].includes(file.type)) {
      reject('请选择 JPG、PNG、WebP 或 GIF 图片。');
      return;
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    error.hidden = true;
    previewUrl = URL.createObjectURL(file);
    image.src = previewUrl;
    field.querySelector('.photo-filename').textContent = file.name;
    preview.hidden = false;
    field.classList.add('has-photo');
    prompt.textContent = '照片已选好';
    action.firstChild.textContent = '更换照片 ';
  });
  image.addEventListener('error', () => reject('这张图片无法预览，请重新选择。'));
  field.querySelector('.photo-remove').addEventListener('click', () => {
    clear();
    input.focus();
  });
})();

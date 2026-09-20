// Actual K1 exports, linked to the device selected on the panel drawing.
import { h, mount, empty } from './dom.js';

const dimensions = (values) => values.map((v) => String(v).replace('.', ',')).join(' × ') + ' mm';
const link = (text, href) => h('a.btn.sm', { text, href, target: '_blank', rel: 'noopener' });

export function createHardwareView(onSelect) {
  const el = h('section.card.hardware-card', { 'aria-label': 'K1 cihaz tasarımları' });
  let selected = 'TC-01';
  let twin = null;
  let signature = '';
  let pcbView = 'pcb3d';

  function select(key, focus = false) {
    if (selected !== key) pcbView = 'pcb3d';
    selected = key;
    signature = '';
    render();
    onSelect(key);
    if (focus) {
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      el.querySelector('h3')?.focus({ preventScroll: true });
    }
  }

  function preview(title, src, alt) {
    const fallback = h('div.empty', { text: 'Görsel yüklenemedi. Teknik dosya bağlantılarını kullanabilirsiniz.', hidden: true });
    const img = h('img', { src, alt, loading: 'lazy',
      onerror: () => { img.hidden = true; fallback.hidden = false; } });
    return h('figure.hardware-figure',
      h('a.hardware-image', { href: src, target: '_blank', rel: 'noopener', 'aria-label': alt + ' · büyüt' }, img),
      fallback, h('figcaption', { text: title + ' · büyütmek için görsele tıkla' }));
  }

  function render() {
    const catalog = twin?.design_catalog;
    if (!catalog?.available) {
      signature = '';
      mount(el, h('header', h('h3', { text: 'K1 cihaz tasarımları' })),
        h('div.body', empty('Tasarım dosyaları bekleniyor',
          'B1 tasarım dosyaları ve güncel sunucu gerekli.')));
      return;
    }
    const devices = (twin.devices || []).filter((d) => catalog.boards[d.hardware_board]);
    const device = devices.find((d) => d.key === selected) || devices[0];
    if (!device) return;
    selected = device.key;
    const design = catalog.boards[device.hardware_board];
    const sig = JSON.stringify([selected, device.x_mm, device.y_mm, design, pcbView]);
    if (sig === signature) return;
    signature = sig;
    const tabs = [['pcb3d', 'PCB 3B'], ['top', 'PCB üst'], ['bottom', 'PCB alt']];
    mount(el,
      h('header', h('h3', { text: `${selected} · ${design.label}`, tabindex: '-1' }),
        h('span.tag', { text: 'K1 / B1' }),
        h('span.sp'), link('Pano montajı · PDF', catalog.report_url)),
      h('div.hardware-select', { role: 'group', 'aria-label': 'Tasarımı gösterilecek cihaz' },
        ...devices.map((d) => h('button.btn.sm' + (d.key === selected ? '.primary' : ''), {
          text: d.key, 'aria-pressed': String(d.key === selected),
          onclick: () => select(d.key),
        }))),
      h('div.body.col',
        h('p.small.muted', { text: `Konum: x ${device.x_mm}, y ${device.y_mm} mm · ${design.mount_tr}` }),
        h('div.hardware-dimensions',
          h('span', { text: 'Kutu: ' + dimensions(design.outer_mm) }),
          h('span', { text: 'PCB: ' + dimensions(design.pcb_mm) })),
        h('div.hardware-previews',
          preview('Mekanik kutu modeli · kapak kaldırılmış', design.images.assembly, `${design.key} B1 mekanik kutu modeli`),
          h('div',
            h('div.hardware-tabs', { role: 'group', 'aria-label': 'PCB görünümü' },
              ...tabs.map(([key, label]) => h('button.btn.sm' + (pcbView === key ? '.primary' : ''), {
                text: label, 'aria-pressed': String(pcbView === key),
                onclick: () => { pcbView = key; signature = ''; render(); },
              }))),
            preview(tabs.find(([key]) => key === pcbView)[1] + ' · KiCad yerleşimi',
              design.images[pcbView], `${design.key} B1 ${tabs.find(([key]) => key === pcbView)[1]}`))),
        h('div.hardware-links',
          link('Şematik · PDF', design.files.schematic),
          link('Kutu · STEP indir', design.files.step),
          link('PCB · KiCad indir', design.files.pcb)),
        h('p.tiny.muted', { text: catalog.note_tr })));
  }

  return { el, select, selected: () => selected,
    update(data) { twin = data; render(); } };
}

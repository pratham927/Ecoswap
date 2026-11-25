import { readFile, mkdir, writeFile, stat } from 'node:fs/promises';
const photos = JSON.parse(await readFile(new URL('../src/photos.json', import.meta.url), 'utf8'));
const directory = new URL('../public/photos/', import.meta.url);
await mkdir(directory, { recursive: true });
for (const photo of photos) {
  for (const width of [900, 1920]) {
    const file = new URL(`${photo.id}-${width}.webp`, directory);
    if (await stat(file).then(s => s.size > 1000).catch(() => false)) continue;
    let error;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const response = await fetch(`${photo.image}?auto=format&fit=crop&fm=webp&q=80&w=${width}`, { signal: AbortSignal.timeout(30000) });
        if (!response.ok || !response.headers.get('content-type')?.startsWith('image/')) throw new Error(`Photo download failed: ${response.status}`);
        const bytes = new Uint8Array(await response.arrayBuffer());
        if (bytes.length < 1000) throw new Error('Photo response is unexpectedly small');
        await writeFile(file, bytes);
        console.log(`Downloaded ${photo.id} (${width}px)`);
        error = null;
        break;
      } catch (caught) { error = caught; }
    }
    if (error) throw error;
  }
}

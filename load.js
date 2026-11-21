// A table of the app (snufish export-app): its JSON index and its float32 binary, kept as base64 text in a hosted
// copy. Shared by the pages and the budget worker, which fetch from the same data/ directory.
export const DATA = "data/";

export async function loadTable(name) {
  const meta = await (await fetch(`${DATA}${name}.json`)).json();
  const response = await fetch(`${DATA}${meta.bin}`);
  if (!response.ok) throw new Error(`could not load ${meta.bin} (${response.status})`);
  if (meta.encoding === "base64") {
    const text = atob((await response.text()).trim()), bytes = new Uint8Array(text.length);
    for (let i = 0; i < text.length; i++) bytes[i] = text.charCodeAt(i);
    return { meta, buffer: bytes.buffer };
  }
  return { meta, buffer: await response.arrayBuffer() };
}

async function handle(res: Response) {
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep status text */
    }
    throw new Error(msg);
  }
  return res.json();
}

const json = (method: string) => (path: string, body?: unknown) =>
  fetch(path, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then(handle);

export const api = {
  get: (path: string) => fetch(path).then(handle),
  post: json("POST"),
  put: json("PUT"),
  del: json("DELETE"),
};

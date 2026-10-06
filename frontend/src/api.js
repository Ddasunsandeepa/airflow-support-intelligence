import { useEffect, useState } from "react";

export async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const data = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      typeof data?.detail === "string"
        ? data.detail
        : `Request failed (${response.status}). Check the API and retry.`,
    );
  return data;
}
export const post = (path, body, signal) =>
  api(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
export function invalidate() {
  window.dispatchEvent(new Event("server-change"));
}

export function useResource(path, interval = 0) {
  const [state, setState] = useState({
    path: null,
    data: null,
    error: "",
    loading: true,
  });
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!path) return;
    let controller;
    let alive = true;
    const refresh = () => {
      controller?.abort();
      controller = new AbortController();
      const signal = controller.signal;
      api(path, { signal })
        .then((data) => {
          if (alive && !signal.aborted)
            setState({ path, data, error: "", loading: false });
        })
        .catch((err) => {
          if (alive && !signal.aborted)
            setState((previous) => ({
              path,
              data: previous.path === path ? previous.data : null,
              error: err.message,
              loading: false,
            }));
        });
    };
    refresh();
    window.addEventListener("focus", refresh);
    window.addEventListener("server-change", refresh);
    const timer = interval ? setInterval(refresh, interval) : null;
    return () => {
      alive = false;
      controller?.abort();
      clearInterval(timer);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("server-change", refresh);
    };
  }, [path, interval, revision]);
  return {
    ...(state.path === path
      ? state
      : { data: null, error: "", loading: Boolean(path) }),
    refresh: () => setRevision((n) => n + 1),
  };
}

export function useRoute() {
  const [route, setRoute] = useState(
    () => location.hash.slice(1) || "/overview",
  );
  useEffect(() => {
    const update = () => {
      setRoute(location.hash.slice(1) || "/overview");
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}
export const incidentPath = (type, id, tab = "investigation") =>
  `/incidents/${type}/${encodeURIComponent(id)}/${tab}`;

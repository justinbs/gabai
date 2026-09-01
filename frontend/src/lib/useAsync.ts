import { useCallback, useEffect, useState } from "react";

type State<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

// Every screen loads, can fail, and needs a retry. Keeping that in one place
// stops four screens from each inventing their own loading flags.
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): {
  state: State<T>;
  reload: () => void;
} {
  const [state, setState] = useState<State<T>>({ status: "loading" });
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });

    load()
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          message:
            cause instanceof Error ? cause.message : "Something went wrong",
        });
      });

    return () => {
      // A resolved promise from a screen the user already left must not write state.
      cancelled = true;
    };
    // The rule cannot see through a spread, and `load` is excluded on purpose:
    // every call site passes an inline arrow whose identity changes each render.
    // Cost of the trade: a wrong `deps` array yields stale data silently.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  return { state, reload };
}

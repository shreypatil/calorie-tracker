/** Session state: who is signed in, and how that changes. */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, setSessionEndedHandler, tokens } from "./api";
import type { TokenPair, User } from "./types";

interface AuthValue {
  user: User | null;
  status: "loading" | "authenticated" | "anonymous";
  signIn: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  // With no stored token the answer is already known, so the first paint is the
  // sign-in screen rather than a blank frame waiting on an effect.
  const [status, setStatus] = useState<AuthValue["status"]>(() =>
    tokens.access ? "loading" : "anonymous",
  );
  const queryClient = useQueryClient();

  const endSession = useCallback(() => {
    tokens.clear();
    setUser(null);
    setStatus("anonymous");
    queryClient.clear();
  }, [queryClient]);

  // A refresh token that stops working mid-session must land the user on the
  // sign-in screen rather than on a page of failed requests.
  useEffect(() => setSessionEndedHandler(endSession), [endSession]);

  // Restore the session on load: a stored token is only a claim until /me agrees.
  useEffect(() => {
    if (!tokens.access) {
      setStatus("anonymous");
      return;
    }
    api
      .get<User>("/auth/me")
      .then((me) => {
        setUser(me);
        setStatus("authenticated");
      })
      .catch(() => endSession());
  }, [endSession]);

  const start = useCallback(async (pair: TokenPair) => {
    tokens.set(pair.access_token, pair.refresh_token);
    setUser(await api.get<User>("/auth/me"));
    setStatus("authenticated");
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      status,
      signIn: async (email, password) => {
        start(await api.post<TokenPair>("/auth/login", { email, password }));
      },
      register: async (email, password, display_name) => {
        await api.post<User>("/auth/register", { email, password, display_name });
        start(await api.post<TokenPair>("/auth/login", { email, password }));
      },
      signOut: async () => {
        const refresh = tokens.refresh;
        // Best effort: the session ends locally whether or not the server is reachable.
        if (refresh) await api.post("/auth/logout", { refresh_token: refresh }).catch(() => {});
        endSession();
      },
    }),
    [user, status, start, endSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// The provider and its hook belong together — splitting them across files to
// satisfy fast refresh would scatter one concept for a dev-only benefit.
// eslint-disable-next-line react/only-export-components
export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

/**
 * The assistant (FR-6) — a transcript, not a messaging app.
 *
 * Speaker identity is carried by an uppercase micro-label and the rule above each block,
 * the same way every other screen separates a heading from its values. There are no bubbles,
 * no avatars, no colour-coded sides, and — per the project's design direction — no motion:
 * the waiting state is a line of text, not a spinner.
 *
 * The one thing this page must never do is imply that something was saved when it was not.
 * A proposed change renders as a `DraftCard` and stays inert until confirmed.
 */

import { useEffect, useRef, useState } from "react";

import { DraftCard } from "../components/chat/DraftCard";
import { PageHeading } from "../components/Layout";
import { Alert, Button, Card, EmptyState, ErrorNote, Loading } from "../components/ui";
import { ApiError } from "../lib/api";
import { cx } from "../lib/cx";
import {
  useChatMessages,
  useClearChat,
  useConfirmAction,
  useDiscardAction,
  useSendMessage,
} from "../lib/queries";
import type { ChatMessage } from "../lib/types";

const SUGGESTIONS = [
  "Log 2 eggs and toast for breakfast",
  "What did I eat today?",
  "Set my calorie goal to 2200",
  "How am I doing this week?",
];

/** Tool rows are provenance, not conversation — one dim line, no payload. */
function ToolTrace({ name }: { name: string | null }) {
  return (
    <p className="py-1 text-[12px] text-ink-muted">
      <span className="eyebrow">Consulted</span> <span className="font-mono">{name}</span>
    </p>
  );
}

function MessageBlock({
  message,
  onConfirm,
  onDiscard,
  busyActionId,
  actionError,
}: {
  message: ChatMessage;
  onConfirm: (id: string, args?: Record<string, unknown>) => void;
  onDiscard: (id: string) => void;
  busyActionId: string | null;
  actionError: { id: string; message: string } | null;
}) {
  if (message.role === "tool") return <ToolTrace name={message.tool_name} />;

  const isUser = message.role === "user";

  return (
    <div className="border-t border-rule py-4 first:border-t-0">
      <p className={cx("eyebrow pb-1.5", isUser && "text-ink-muted")}>
        {isUser ? "You" : "Assistant"}
      </p>
      {message.content && (
        <p className="whitespace-pre-wrap text-[14px] leading-relaxed">{message.content}</p>
      )}
      {message.actions.map((action) => (
        <DraftCard
          key={action.id}
          action={action}
          busy={busyActionId === action.id}
          error={actionError?.id === action.id ? actionError.message : undefined}
          onConfirm={(args) => onConfirm(action.id, args)}
          onDiscard={() => onDiscard(action.id)}
        />
      ))}
    </div>
  );
}

export function Chat() {
  const messages = useChatMessages();
  const send = useSendMessage();
  const confirm = useConfirmAction();
  const discard = useDiscardAction();
  const clear = useClearChat();

  const [draft, setDraft] = useState("");
  const [actionError, setActionError] = useState<{ id: string; message: string } | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  // Keep the newest turn in view. `auto` rather than `smooth`: this app has no motion.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.data?.length, send.isPending]);

  const submit = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || send.isPending) return;
    setDraft("");
    send.mutate(trimmed);
  };

  const runAction = (id: string, args?: Record<string, unknown>) => {
    setActionError(null);
    confirm.mutate(
      { id, args },
      {
        onError: (error) =>
          setActionError({
            id,
            message:
              error instanceof ApiError
                ? (Object.values(error.fieldErrors)[0] ?? error.message)
                : "Could not apply that change.",
          }),
      },
    );
  };

  const busyActionId = confirm.isPending
    ? confirm.variables?.id
    : discard.isPending
      ? discard.variables
      : null;

  const items = messages.data ?? [];

  return (
    <>
      <PageHeading
        title="Assistant"
        description="Log meals, set goals and ask about your intake in plain language. Changes are always shown for review before they are saved."
        actions={
          items.length > 0 ? (
            <Button
              onClick={() => clear.mutate()}
              disabled={clear.isPending}
              variant="danger"
            >
              Clear conversation
            </Button>
          ) : undefined
        }
      />

      <Card className="flex min-h-[60vh] flex-col">
        <div className="flex-1 px-5 py-2">
          {messages.isLoading ? (
            <Loading label="Loading conversation" />
          ) : messages.error ? (
            <ErrorNote error={messages.error} />
          ) : items.length === 0 ? (
            <EmptyState
              title="Nothing here yet"
              description="Ask a question or describe what you ate. The assistant can log meals, change your goals and read back your history — and it always asks before saving anything."
            />
          ) : (
            items.map((message) => (
              <MessageBlock
                key={message.id}
                message={message}
                onConfirm={runAction}
                onDiscard={(id) => {
                  setActionError(null);
                  discard.mutate(id);
                }}
                busyActionId={busyActionId ?? null}
                actionError={actionError}
              />
            ))
          )}

          {send.isPending && (
            <p className="border-t border-rule py-4 text-[13px] text-ink-muted">Thinking…</p>
          )}
          <div ref={endRef} />
        </div>

        <div className="border-t border-rule px-5 py-4">
          {send.error && (
            <div className="pb-3">
              <Alert>
                {send.error instanceof Error ? send.error.message : "Could not send that."}
              </Alert>
            </div>
          )}

          {items.length === 0 && (
            <div className="flex flex-wrap gap-2 pb-3">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => submit(suggestion)}
                  className="rounded border border-rule px-2.5 py-1 text-[12px] text-ink-soft hover:bg-paper"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          )}

          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              submit(draft);
            }}
          >
            <label className="sr-only" htmlFor="chat-message">
              Message
            </label>
            <input
              id="chat-message"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Log 2 eggs and toast for breakfast…"
              autoComplete="off"
              className="w-full rounded border border-rule bg-surface px-2.5 py-1.5 text-[14px] placeholder:text-ink-muted focus:border-accent"
            />
            <Button type="submit" variant="primary" disabled={send.isPending || !draft.trim()}>
              Send
            </Button>
          </form>
        </div>
      </Card>
    </>
  );
}

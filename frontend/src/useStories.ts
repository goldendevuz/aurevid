// SPDX-License-Identifier: AGPL-3.0-or-later
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { isStoryFinished, watchStory } from "./stories";
import type { Story } from "./types";

/** Your newest stories, kept fresh while any is still generating or joining. */
export function useStories(limit: number, onChanged?: () => void) {
  const [stories, setStories] = useState<Story[]>([]);
  const watchers = useRef(new Map<string, () => void>());
  const changed = useRef(onChanged);
  useEffect(() => {
    changed.current = onChanged;
  }, [onChanged]);

  const upsert = useCallback((story: Story) => {
    setStories((prev) => [story, ...prev.filter((s) => s.id !== story.id)].sort((a, b) => b.created_at.localeCompare(a.created_at)));
    if (isStoryFinished(story)) {
      watchers.current.delete(story.id);
      changed.current?.(); // credit balance (refunds), provider quotas
    }
  }, []);

  const watch = useCallback(
    (id: string) => {
      if (!watchers.current.has(id)) watchers.current.set(id, watchStory(id, upsert));
    },
    [upsert],
  );

  const load = useCallback(async () => {
    const list = await api<Story[]>(`/api/stories?limit=${limit}`);
    setStories(list);
    list.filter((s) => !isStoryFinished(s)).forEach((s) => watch(s.id));
  }, [limit, watch]);

  useEffect(() => {
    const current = watchers.current;
    return () => current.forEach((stop) => stop());
  }, []);

  const track = useCallback(
    (story: Story) => {
      upsert(story);
      if (!isStoryFinished(story)) watch(story.id);
    },
    [upsert, watch],
  );

  const retryScene = useCallback(
    async (story: Story, index: number) => {
      track(await api<Story>(`/api/stories/${story.id}/scenes/${index}/retry`, { method: "POST" }));
      changed.current?.();
    },
    [track],
  );

  const restitch = useCallback(
    async (story: Story) => track(await api<Story>(`/api/stories/${story.id}/stitch`, { method: "POST" })),
    [track],
  );

  const remove = useCallback(async (story: Story) => {
    await api(`/api/stories/${story.id}`, { method: "DELETE" });
    watchers.current.get(story.id)?.();
    watchers.current.delete(story.id);
    setStories((prev) => prev.filter((s) => s.id !== story.id));
  }, []);

  return { stories, load, track, retryScene, restitch, remove };
}

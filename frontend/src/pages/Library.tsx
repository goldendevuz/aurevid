// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Icon } from "../components/icons";
import { Button } from "../components/ui";
import JobCard from "../components/JobCard";
import StoryCard from "../components/StoryCard";
import { useStories } from "../useStories";
import type { Job } from "../types";

export default function Library() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "image" | "video" | "story" | "favorites">("all");
  const [isListView, setIsListView] = useState(false);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const { stories, load: loadStories, retryScene, restitch, remove: removeStory } = useStories(20);

  useEffect(() => {
    void (async () => {
      setLoading(true);
      try {
        const recent = await api<Job[]>("/api/jobs?limit=50");
        setJobs(recent.filter((j) => j.status === "done" && j.assets.length > 0));
        await loadStories();
      } catch {
        /* ignore */
      } finally {
        setLoading(false);
      }
    })();
  }, [loadStories]);

  const items = useMemo(() => {
    const list = [
      ...jobs.map((job) => ({ at: job.created_at, job, kind: job.kind })),
      ...stories.map((story) => ({ at: story.created_at, story, kind: "story" })),
    ].sort((a, b) => b.at.localeCompare(a.at));

    if (filter === "all") return list;
    if (filter === "image") return list.filter((i) => i.kind === "image");
    if (filter === "video") return list.filter((i) => i.kind === "video");
    if (filter === "story") return list.filter((i) => i.kind === "story");
    if (filter === "favorites") {
      return list.filter((i) => {
        if ("job" in i) return i.job.assets.some((a) => a.is_favorite);
        return false;
      });
    }
    return list;
  }, [jobs, stories, filter]);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const handleBulkDownload = () => {
    const selectedAssets = jobs
      .filter((j) => selectedIds.includes(j.id))
      .flatMap((j) => j.assets);
    selectedAssets.forEach((a) => {
      const link = document.createElement("a");
      link.href = a.url;
      link.download = `aurevid-${a.id}.${a.mime.includes("video") ? "mp4" : "png"}`;
      link.click();
    });
  };

  const handleBulkDelete = async () => {
    if (!window.confirm(`Delete ${selectedIds.length} items from your library?`)) return;
    for (const id of selectedIds) {
      try {
        await api(`/api/jobs/${id}`, { method: "DELETE" });
      } catch {
        /* ignore */
      }
    }
    setJobs((prev) => prev.filter((j) => !selectedIds.includes(j.id)));
    setSelectedIds([]);
    setSelectionMode(false);
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 space-y-6">
      {/* Top Header & Toolbar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Media Library</h1>
          <p className="text-xs text-muted mt-1">Browse, filter, and export all your completed images and videos.</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {selectionMode ? (
            <>
              <span className="text-xs font-mono text-muted mr-1">{selectedIds.length} selected</span>
              <Button size="sm" disabled={selectedIds.length === 0} onClick={handleBulkDownload}>
                <Icon name="download" size={13} />
                Download
              </Button>
              <Button size="sm" variant="danger" disabled={selectedIds.length === 0} onClick={() => void handleBulkDelete()}>
                <Icon name="trash" size={13} />
                Delete
              </Button>
              <Button size="sm" variant="ghost" onClick={() => { setSelectionMode(false); setSelectedIds([]); }}>
                Cancel
              </Button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => setSelectionMode(true)}
                className="rounded-xl border border-line bg-surface-1 px-3 py-1.5 text-xs font-medium text-muted hover:text-ink hover:border-white/20 transition"
              >
                Select Mode
              </button>
              <button
                type="button"
                onClick={() => setIsListView((v) => !v)}
                className="grid h-8 w-8 place-items-center rounded-xl border border-line bg-surface-1 text-muted hover:text-ink transition"
                title={isListView ? "Grid view" : "List view"}
              >
                <Icon name={isListView ? "layers" : "image"} size={14} />
              </button>
            </>
          )}
        </div>
      </div>

      {/* Filter Chips Bar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-line pb-4">
        {(["all", "image", "video", "story", "favorites"] as const).map((chip) => {
          const active = filter === chip;
          return (
            <button
              key={chip}
              type="button"
              onClick={() => setFilter(chip)}
              className={`rounded-full px-3.5 py-1.5 text-xs font-medium capitalize transition ${
                active ? "bg-accent text-accent-ink font-semibold" : "border border-line bg-surface-1 text-muted hover:text-ink hover:bg-surface-2"
              }`}
            >
              {chip}
            </button>
          );
        })}
      </div>

      {/* Library Grid / List Content */}
      {loading ? (
        <div className="py-20 text-center text-sm text-muted">Loading your media assets...</div>
      ) : items.length === 0 ? (
        <div className="py-20 text-center max-w-md mx-auto">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-surface-2 text-muted mx-auto mb-3">
            <Icon name="image" size={24} />
          </div>
          <h3 className="text-lg font-semibold text-ink">No Media Found</h3>
          <p className="mt-1 text-xs text-muted leading-relaxed">
            {filter === "all"
              ? "You haven't generated any images or videos yet. Start creating in the studio!"
              : `No assets match the "${filter}" filter.`}
          </p>
          <Link
            to="/create"
            className="mt-5 inline-flex items-center gap-1.5 rounded-full bg-accent px-4 py-2 text-xs font-semibold text-accent-ink hover:bg-accent/90 transition"
          >
            <Icon name="sparkle" size={14} />
            Go to Studio
          </Link>
        </div>
      ) : (
        <div
          className={`grid gap-4 ${
            isListView
              ? "grid-cols-1"
              : "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4"
          }`}
        >
          {items.map((item, i) => {
            if ("story" in item) {
              return (
                <StoryCard
                  key={item.story.id}
                  story={item.story}
                  index={i}
                  onRetryScene={retryScene}
                  onRestitch={restitch}
                  onDelete={removeStory}
                />
              );
            }
            const isSelected = selectedIds.includes(item.job.id);
            return (
              <div key={item.job.id} className="relative group">
                {selectionMode && (
                  <button
                    type="button"
                    onClick={() => toggleSelect(item.job.id)}
                    className={`absolute left-3 top-3 z-20 grid h-6 w-6 place-items-center rounded-md border text-black transition ${
                      isSelected ? "border-accent bg-accent" : "border-white/50 bg-black/60 text-transparent"
                    }`}
                  >
                    <Icon name="check" size={14} strokeWidth={3} />
                  </button>
                )}
                <JobCard
                  job={item.job}
                  index={i}
                  onChange={(updated) => setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)))}
                  onDelete={async (j) => {
                    await api(`/api/jobs/${j.id}`, { method: "DELETE" });
                    setJobs((prev) => prev.filter((x) => x.id !== j.id));
                  }}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

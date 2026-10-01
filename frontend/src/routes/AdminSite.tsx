import { useState } from "react";

import * as api from "../api/client";
import { ApiError } from "../api/http";
import type { Category, ThemePreset } from "../api/types";
import { Button, ErrorState, Input, Loading, PageHeading } from "../components/ui";
import { THEMES } from "../lib/themes";
import { useAsync } from "../lib/useAsync";
import { usePageTitle } from "../lib/usePageTitle";
import { useSite } from "../site-context";

// Site details, colour, logo and categories.
export function AdminSite() {
  usePageTitle("Site settings");
  const { loaded, failed, refresh } = useSite();
  const [message, setMessage] = useState("");
  const say = (text: string) => setMessage(text);

  return (
    <>
      <PageHeading title="Site settings" description="What residents see, and how requests are sorted" />
      <p
        role="status"
        aria-live="polite"
        className={message ? "mb-6 border-l-4 border-brand pl-3 font-bold" : "sr-only"}
      >
        {message}
      </p>
      {loaded ? (
        <>
          <Details onSaved={say} />
          <Colour onSaved={say} />
          <Logo onSaved={say} />
        </>
      ) : failed ? (
        <ErrorState description="Couldn't load the site settings" onRetry={() => refresh()} />
      ) : (
        <Loading />
      )}
      <Categories onSaved={say} />
    </>
  );
}

function Section({ title, hint, children }: { title: string; hint: string; children: React.ReactNode }) {
  return (
    <section className="mb-12 max-w-3xl">
      <h2 className="text-[24px] font-bold">{title}</h2>
      <p className="mt-1 text-muted">{hint}</p>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function errorText(err: unknown): string {
  return err instanceof ApiError ? err.message : "Didn't save, try again";
}

function Details({ onSaved }: { onSaved: (text: string) => void }) {
  const { site, setSite } = useSite();
  const [draft, setDraft] = useState({
    barangay_name: site.barangay_name,
    place: site.place,
    address: site.address ?? "",
    hotline: site.hotline ?? "",
    office_hours: site.office_hours ?? "",
  });
  const [busy, setBusy] = useState(false);
  const set = (field: keyof typeof draft) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setDraft({ ...draft, [field]: e.target.value });

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!draft.barangay_name.trim() || !draft.place.trim()) {
      onSaved("The barangay name and place can't be empty");
      return;
    }
    setBusy(true);
    try {
      const saved = await api.updateSite({
        barangay_name: draft.barangay_name.trim(),
        place: draft.place.trim(),
        address: draft.address.trim() || null,
        hotline: draft.hotline.trim() || null,
        office_hours: draft.office_hours.trim() || null,
      });
      setSite(saved);
      onSaved("Barangay details saved");
    } catch (err) {
      onSaved(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section
      title="Barangay details"
      hint="Empty fields are hidden. Enter only what the barangay confirmed"
    >
      <form onSubmit={save} noValidate className="grid gap-5">
        <Input id="site-name" label="Barangay name" value={draft.barangay_name} onChange={set("barangay_name")} maxLength={100} />
        <Input id="site-place" label="Place" hint="For example: Amaya, Tanza, Cavite" value={draft.place} onChange={set("place")} maxLength={100} />
        <Input id="site-address" label="Office address" value={draft.address} onChange={set("address")} maxLength={200} />
        <Input id="site-hotline" label="Hotline" value={draft.hotline} onChange={set("hotline")} maxLength={50} />
        <Input id="site-hours" label="Office hours" hint="For example: Monday to Friday, 8 AM to 5 PM" value={draft.office_hours} onChange={set("office_hours")} maxLength={100} />
        <div>
          <Button type="submit" disabled={busy}>
            {busy ? "Saving" : "Save details"}
          </Button>
        </div>
      </form>
    </Section>
  );
}

function Colour({ onSaved }: { onSaved: (text: string) => void }) {
  const { site, setSite } = useSite();
  const [choice, setChoice] = useState<ThemePreset>(site.theme);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      const saved = await api.updateSite({ theme: choice });
      setSite(saved);
      onSaved(`Colour changed to ${THEMES[choice].label.toLowerCase()}`);
    } catch (err) {
      onSaved(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section title="Colour" hint="Main colour of buttons and headings">
      <fieldset>
        <legend className="sr-only">Main colour</legend>
        <div className="flex flex-wrap gap-3">
          {(Object.keys(THEMES) as ThemePreset[]).map((name) => (
            <label
              key={name}
              className={`flex cursor-pointer items-center gap-3 border-2 px-3 py-2 ${
                choice === name ? "border-ink" : "border-rule"
              }`}
            >
              <input
                type="radio"
                name="theme"
                value={name}
                checked={choice === name}
                onChange={() => setChoice(name)}
                className="h-5 w-5 accent-ink"
              />
              <span aria-hidden="true" className="h-7 w-7" style={{ background: THEMES[name].brand }} />
              {THEMES[name].label}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="mt-4">
        <Button onClick={save} disabled={busy || choice === site.theme}>
          {busy ? "Saving" : "Save colour"}
        </Button>
      </div>
    </Section>
  );
}

function Logo({ onSaved }: { onSaved: (text: string) => void }) {
  const { site, setSite, logoUrl } = useSite();
  const [busy, setBusy] = useState(false);

  const upload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    // Also checked on the server.
    if (!api.LOGO_TYPES.includes(file.type)) {
      onSaved("Pick a PNG, JPEG or WebP image");
      return;
    }
    if (file.size > api.MAX_LOGO_BYTES) {
      onSaved("The logo has to be 1 MB or smaller");
      return;
    }
    setBusy(true);
    try {
      setSite(await api.uploadLogo(file));
      onSaved("Logo changed");
    } catch (err) {
      onSaved(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    setBusy(true);
    try {
      setSite(await api.removeLogo());
      onSaved("Back to the default logo");
    } catch (err) {
      onSaved(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section
      title="Logo"
      hint="Only a logo the barangay owns or allows. PNG, JPEG or WebP, up to 1 MB"
    >
      <div className="flex flex-wrap items-center gap-6">
        <img src={logoUrl} alt="Current logo" className="h-24 w-24 border border-rule object-contain" />
        <div className="flex flex-wrap items-center gap-4">
          <label className="inline-flex cursor-pointer bg-wash px-5 py-2.5 font-bold shadow-[0_3px_0_#929191] focus-within:bg-focus focus-within:text-ink focus-within:shadow-[0_3px_0_#0b0c0c]">
            {busy ? "Uploading" : "Upload a new logo"}
            <input type="file" accept={api.LOGO_TYPES.join(",")} onChange={upload} disabled={busy} className="sr-only" />
          </label>
          {site.logo_version && (
            <Button variant="secondary" onClick={reset} disabled={busy}>
              Use the default logo
            </Button>
          )}
        </div>
      </div>
    </Section>
  );
}

function Categories({ onSaved }: { onSaved: (text: string) => void }) {
  const { state, reload } = useAsync(() => api.listAllCategories(), []);
  return (
    <Section
      title="Categories"
      hint="Switched off sends its requests to review. Categories can't be added"
    >
      {state.status === "loading" && <Loading />}
      {state.status === "error" && <ErrorState description={state.message} onRetry={reload} />}
      {state.status === "ready" && (
        <div className="grid gap-6">
          {state.data.map((category) => (
            <CategoryRow key={category.id} category={category} onSaved={(text) => { onSaved(text); reload(); }} />
          ))}
        </div>
      )}
    </Section>
  );
}

function CategoryRow({ category, onSaved }: { category: Category; onSaved: (text: string) => void }) {
  const [name, setName] = useState(category.name);
  const [description, setDescription] = useState(category.description ?? "");
  const [busy, setBusy] = useState(false);
  const changed = name.trim() !== category.name || (description.trim() || null) !== category.description;

  const save = async (changes: Parameters<typeof api.updateCategory>[1], done: string) => {
    setBusy(true);
    try {
      await api.updateCategory(category.id, changes);
      onSaved(done);
    } catch (err) {
      onSaved(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`border-l-4 pl-4 ${category.is_active ? "border-brand" : "border-rule"}`}>
      <p className="text-[15px] text-muted">
        {category.is_active ? "On" : "Off"} · label the system uses: {category.slug}
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!name.trim()) {
            onSaved("A category needs a name");
            return;
          }
          save({ name: name.trim(), description: description.trim() || null }, `${name.trim()} saved`);
        }}
        className="mt-2 grid gap-3"
      >
        <Input id={`cat-name-${category.id}`} label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} />
        <Input
          id={`cat-desc-${category.id}`}
          label="What belongs here"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={500}
        />
        <div className="flex flex-wrap gap-4">
          <Button type="submit" disabled={busy || !changed}>
            Save
          </Button>
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => {
              if (
                category.is_active &&
                !window.confirm(`Switch off ${category.name}? New requests the system puts there will go to review`)
              ) {
                return;
              }
              save(
                { is_active: !category.is_active },
                `${category.name} switched ${category.is_active ? "off" : "on"}`,
              );
            }}
          >
            {category.is_active ? "Switch off" : "Switch on"}
          </Button>
        </div>
      </form>
    </div>
  );
}

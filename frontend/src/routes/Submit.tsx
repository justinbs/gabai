import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import * as api from "../api/client";
import { Button, FOCUS_LINK, PageHeading, Textarea } from "../components/ui";
import { usePageTitle } from "../lib/usePageTitle";
import type { ServiceRequest } from "../api/types";

const MIN_LENGTH = 10;
const MAX_LENGTH = 5000;

export function Submit() {
  usePageTitle("Report a concern");
  const navigate = useNavigate();
  const fileInput = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [uploads, setUploads] = useState<File[]>([]);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<ServiceRequest | null>(null);

  const reject = (message: string) => {
    setUploads([]);
    if (fileInput.current) fileInput.current.value = "";
    setError(message);
  };

  const pick = (list: FileList | null) => {
    if (!list) return;
    const chosen = Array.from(list);

    const tooBig = chosen.find((f) => f.size > api.MAX_FILE_BYTES);
    if (tooBig) {
      reject(`${tooBig.name} is over 5 MB · lampas 5 MB ang ${tooBig.name}`);
      return;
    }
    const wrongType = chosen.find((f) => !api.ALLOWED_TYPES.includes(f.type));
    if (wrongType) {
      reject(`${wrongType.name} isn't a photo or PDF · hindi ito larawan o PDF`);
      return;
    }
    setError(undefined);
    setUploads(chosen);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (text.trim().length < MIN_LENGTH) {
      setError("Tell us a bit more · Kulang pa po ang detalye");
      return;
    }
    setError(undefined);
    setBusy(true);
    try {
      setCreated(await api.submitRequest(text.trim(), uploads));
    } catch {
      setError("Didn't send, try again · Hindi naipadala, subukan po muli");
    } finally {
      setBusy(false);
    }
  };

  if (created) {
    return (
      <>
        <PageHeading
          title="Thanks, we got your request"
          description="Salamat po, natanggap na namin ang inyong request"
        />

        <p className="font-mono text-[36px] font-bold tracking-tight">
          {created.reference_number}
        </p>
        <p className="mt-2 text-[19px]">Keep this number for follow ups</p>
        <p className="text-muted">Itago po ninyo ang numerong ito</p>

        <h2 className="mt-8 text-[24px] font-bold">
          What happens next · Ano ang susunod
        </h2>
        <p className="mt-2 text-[19px]">
          We'll pass this to the right person and you'll see updates here
        </p>
        <p className="text-muted">
          Ipapasa po namin ito sa tamang tanggapan, makikita ninyo dito ang mga
          update
        </p>

        <p className="mt-4 text-[19px]">
          How long depends on what you reported and how busy the office is
        </p>
        <p className="text-muted">
          Depende po sa iniulat ninyo at sa dami ng ginagawa ng tanggapan
        </p>

        <div className="mt-8 flex flex-wrap gap-3">
          <Button onClick={() => navigate(`/requests/${created.id}`)}>
            View this request · Tingnan
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              setCreated(null);
              setText("");
              setUploads([]);
            }}
          >
            Report something else · Mag-report ulit
          </Button>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeading title="Report a concern" />
      <p className="mb-6 text-[19px] text-muted">
        Tagalog, English, or a mix · Tagalog, English, o halo
      </p>

      <form onSubmit={submit} noValidate>
        <Textarea
          name="description"
          label="What is your concern? · Ano po ang inyong hinaing?"
          hint="Where it's happening, and why it's urgent · Saan ito nangyayari, at bakit madalian"
          rows={7}
          maxLength={MAX_LENGTH}
          value={text}
          error={error}
          onChange={(e) => setText(e.target.value)}
        />
        <p className="mt-2 text-right text-muted">
          {text.length} / {MAX_LENGTH}
        </p>

        <div className="mt-6">
          <label htmlFor="photos" className="block text-[19px] font-bold">
            Photos · Mga larawan
          </label>
          <p id="photos-hint" className="mt-1 text-muted">
            Optional, up to 5 MB each · Opsyonal, hanggang 5 MB bawat isa
          </p>
          <input
            ref={fileInput}
            id="photos"
            name="photos"
            type="file"
            multiple
            accept={api.ALLOWED_TYPES.join(",")}
            aria-describedby="photos-hint"
            onChange={(e) => pick(e.target.files)}
            className={`mt-2 block w-full border-2 border-ink p-2 text-[17px] file:mr-3 file:border-0 file:bg-wash file:px-3 file:py-1.5 file:font-bold ${FOCUS_LINK}`}
          />
          {uploads.length > 0 && (
            <ul className="mt-2">
              {uploads.map((f) => (
                <li key={f.name} className="text-muted">
                  {f.name} ({Math.round(f.size / 1024)} KB)
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-4">
          <Button type="submit" disabled={busy}>
            {busy ? "Sending" : "Send · Ipadala"}
          </Button>
          <Link to="/requests" className={`text-link underline ${FOCUS_LINK}`}>
            Cancel · Kanselahin
          </Link>
        </div>
      </form>
    </>
  );
}
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import * as api from "../api/client";
import { Button, FOCUS_LINK, Help, PageHeading, Textarea } from "../components/ui";
import { shrinkPhoto } from "../lib/photos";
import { usePageTitle } from "../lib/usePageTitle";
import { useUser } from "../session-context";
import type { ServiceRequest } from "../api/types";

const MIN_LENGTH = 10;
const MAX_LENGTH = 5000;

export function Submit() {
  usePageTitle("Report a concern");
  const navigate = useNavigate();
  const user = useUser();
  const fileInput = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [uploads, setUploads] = useState<File[]>([]);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const [created, setCreated] = useState<ServiceRequest | null>(null);
  // Files that didn't upload after the request was created.
  const [failed, setFailed] = useState<File[]>([]);
  const [retried, setRetried] = useState(false);
  const latestPick = useRef(0);

  // Ask before leaving while something is still being sent.
  useEffect(() => {
    if (!busy) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [busy]);

  const reject = (message: string) => {
    setUploads([]);
    if (fileInput.current) fileInput.current.value = "";
    setError(message);
  };

  const pick = async (list: FileList | null) => {
    if (!list) return;
    const chosen = Array.from(list);
    // Only the latest pick counts if the person picks again while one is running.
    const pickId = ++latestPick.current;

    const wrongType = chosen.find((f) => !api.ALLOWED_TYPES.includes(f.type));
    if (wrongType) {
      setPreparing(false);
      reject(`${wrongType.name} isn't a photo or PDF · hindi ito larawan o PDF`);
      return;
    }
    // Shrink photos first, so a large phone photo isn't refused for its size.
    setError(undefined);
    setPreparing(true);
    const prepared: File[] = [];
    for (const file of chosen) prepared.push(await shrinkPhoto(file));
    if (pickId !== latestPick.current) return;
    setPreparing(false);

    const tooBig = prepared.find((f) => f.size > api.MAX_FILE_BYTES);
    if (tooBig) {
      reject(`${tooBig.name} is over 5 MB · lampas 5 MB ang ${tooBig.name}`);
      return;
    }
    setUploads(prepared);
  };

  // Sends the files one at a time. Returns the ones that didn't go through.
  const sendFiles = async (requestId: number, files: File[]): Promise<File[]> => {
    for (let i = 0; i < files.length; i++) {
      setProgress(
        `Sending file ${i + 1} of ${files.length} · Ipinapadala ang file ${i + 1} sa ${files.length}`,
      );
      try {
        await api.uploadAttachment(requestId, files[i]);
      } catch {
        return files.slice(i);
      }
    }
    return [];
  };

  const refreshed = async (request: ServiceRequest) => {
    try {
      return (await api.getRequest(user, request.id)) ?? request;
    } catch {
      return request;
    }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (text.trim().length < MIN_LENGTH) {
      setError("Tell us a bit more · Kulang pa po ang detalye");
      return;
    }
    setError(undefined);
    setBusy(true);
    setProgress("");
    let request: ServiceRequest;
    try {
      request = await api.createRequest(text.trim());
    } catch {
      setError("Didn't send, try again · Hindi naipadala, subukan po muli");
      setBusy(false);
      return;
    }
    const left = await sendFiles(request.id, uploads);
    setFailed(left);
    setCreated(uploads.length > 0 ? await refreshed(request) : request);
    setBusy(false);
    setProgress("");
  };

  const retry = async () => {
    if (!created) return;
    setBusy(true);
    const left = await sendFiles(created.id, failed);
    setFailed(left);
    setRetried(left.length === 0);
    setCreated(await refreshed(created));
    setBusy(false);
    setProgress("");
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

        {failed.length > 0 && (
          <div role="alert" className="mt-6 border-l-4 border-ink bg-wash p-4">
            <p className="text-[19px] font-bold">
              {failed.length === 1
                ? "Your report was sent, but the photo didn't upload"
                : `Your report was sent, but ${failed.length} photos didn't upload`}
            </p>
            <p className="text-muted">
              {failed.length === 1
                ? "Naipadala na ang inyong report, pero hindi na-upload ang larawan"
                : `Naipadala na ang inyong report, pero hindi na-upload ang ${failed.length} larawan`}
            </p>
            <div className="mt-3">
              <Button onClick={retry} disabled={busy}>
                {busy
                  ? progress
                  : failed.length === 1
                    ? "Try the photo again · Subukan ulit ang larawan"
                    : "Try the photos again · Subukan ulit ang mga larawan"}
              </Button>
            </div>
          </div>
        )}
        {retried && failed.length === 0 && (
          <p role="status" className="mt-6 text-[19px] font-bold">
            Photos uploaded · Na-upload na ang mga larawan
          </p>
        )}

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
              setFailed([]);
              setRetried(false);
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
      <Help title="How to report · Paano mag-report">
        <p>Say what happened, where (purok, street or landmark), and since when. Filipino, English or Taglish are all fine.<span className="block text-muted">Sabihin kung ano ang nangyari, saan (purok, kalye o palatandaan), at kailan pa. Puwede ang Filipino, English o Taglish.</span></p>
        <p>Add photos if they help. JPEG, PNG, WebP or PDF. Photos are made smaller before sending. PDFs can be up to 5 MB.<span className="block text-muted">Magdagdag ng litrato kung makakatulong. JPEG, PNG, WebP o PDF. Pinapaliit muna ang litrato bago ipadala. Hanggang 5 MB ang PDF.</span></p>
        <p>The system sorts your report and sends it to the staff member who handles that concern, or a staff member sorts it first. You get a reference number to follow it.<span className="block text-muted">Aayusin ng sistema ang inyong report at ipapadala sa staff na humahawak nito, o isang staff muna ang mag-aayos nito. Makakakuha kayo ng reference number para masubaybayan ito.</span></p>
        <p>In an emergency, call 911 or go to the barangay hall right away.<span className="block text-muted">Kung emergency, tumawag sa 911 o pumunta agad sa barangay hall.</span></p>
      </Help>
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
            Optional, PDFs up to 5 MB · Opsyonal, hanggang 5 MB ang PDF
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
              {uploads.map((f, i) => (
                <li key={i} className="text-muted">
                  {f.name} ({Math.round(f.size / 1024)} KB)
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-4">
          <Button type="submit" disabled={busy || preparing}>
            {preparing
              ? "Preparing photos · Inihahanda ang mga larawan"
              : busy
                ? progress || "Sending · Ipinapadala"
                : "Send · Ipadala"}
          </Button>
          <Link to="/requests" className={`text-link underline ${FOCUS_LINK}`}>
            Cancel · Kanselahin
          </Link>
        </div>
      </form>
    </>
  );
}
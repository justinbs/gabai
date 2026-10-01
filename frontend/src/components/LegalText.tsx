import type { LegalDoc } from "../content/terms";

// Renders one legal document.
export function LegalText({ doc, level = 2 }: { doc: LegalDoc; level?: 2 | 3 }) {
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <div className="max-w-[70ch]">
      <p className="border-l-4 border-brand bg-wash p-4 text-[19px]">{doc.summary}</p>
      {doc.sections.map((section) => (
        <section key={section.heading} className="mt-8">
          <Heading className="text-[24px] font-bold leading-tight">{section.heading}</Heading>
          {section.items && (
            <ul className="mt-3 list-disc space-y-2 pl-6">
              {section.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
          {section.paragraphs?.map((text) => (
            <p key={text} className="mt-3">
              {text}
            </p>
          ))}
        </section>
      ))}
    </div>
  );
}

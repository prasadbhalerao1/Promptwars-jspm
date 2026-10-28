/**
 * `html2pdf.js` ships no type declarations and has no `@types/html2pdf.js` package, so
 * importing it was an implicit-`any` error under `noImplicitAny` (the only error left in
 * `tsc --noEmit`). This declares the narrow slice of the chainable API that
 * `AtsResumeBuilder.tsx` actually uses.
 */
declare module "html2pdf.js" {
  interface Html2PdfOptions {
    margin?: number | [number, number, number, number];
    filename?: string;
    image?: { type?: string; quality?: number };
    html2canvas?: { scale?: number; useCORS?: boolean; [key: string]: unknown };
    jsPDF?: { unit?: string; format?: string | number[]; orientation?: string };
    pagebreak?: { mode?: string | string[]; before?: string; after?: string };
    [key: string]: unknown;
  }

  interface Html2Pdf {
    set(options: Html2PdfOptions): Html2Pdf;
    from(element: HTMLElement | string): Html2Pdf;
    save(filename?: string): Promise<void>;
    toPdf(): Html2Pdf;
    outputPdf(type?: string): Promise<unknown>;
    then(onfulfilled?: (value: unknown) => unknown): Promise<unknown>;
  }

  function html2pdf(): Html2Pdf;
  function html2pdf(
    element: HTMLElement | string,
    options?: Html2PdfOptions,
  ): Html2Pdf;

  export default html2pdf;
}

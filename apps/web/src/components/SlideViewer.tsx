import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SlideOut } from "@/lib/api";

export function SlideViewer({ slides }: { slides: SlideOut[] }) {
  if (slides.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No slide content could be extracted from this deck.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {slides.map((slide) => (
        <Card key={slide.slide_index} id={`slide-${slide.slide_index + 1}`} className="scroll-mt-20">
          <CardHeader>
            <CardTitle className="font-heading text-base flex items-center justify-between">
              <span>
                Slide {slide.slide_index + 1}
                {slide.title ? `: ${slide.title}` : ""}
              </span>
              <span className="text-xs font-mono font-normal text-muted-foreground">
                #{slide.slide_index + 1}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {slide.body && (
              <p className="whitespace-pre-wrap text-foreground">
                {slide.body}
              </p>
            )}
            {slide.notes && (
              <p className="whitespace-pre-wrap text-xs text-muted-foreground">
                <span className="font-medium">Speaker notes: </span>
                {slide.notes}
              </p>
            )}
            {slide.has_image && slide.ocr_text && (
              <p className="text-xs text-muted-foreground">
                <span className="font-medium">Image/diagram: </span>
                {slide.ocr_text}
              </p>
            )}
            {!slide.body && !slide.notes && !slide.ocr_text && (
              <p className="text-xs text-muted-foreground">
                No text extracted from this slide.
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

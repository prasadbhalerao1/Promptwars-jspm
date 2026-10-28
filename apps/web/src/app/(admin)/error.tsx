"use client";

import { RouteError } from "@/components/common/RouteError";

export default function Error(props: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RouteError {...props} area="Admin tools" />;
}

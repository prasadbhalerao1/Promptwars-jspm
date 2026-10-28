"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function NotFoundPage() {
  return (
    <div className="flex flex-col flex-1 items-center justify-center min-h-[70vh] p-6 bg-card">
      <Card className="max-w-md w-full text-center shadow-flat">
        <CardHeader className="space-y-2">
          <div className="text-4xl font-semibold text-primary">404</div>
          <CardTitle className="text-xl font-bold text-foreground">
            Page Not Found
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground">
            The page or workspace route you are looking for does not exist or
            has been moved.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-2">
          <Button render={<Link href="/home" />} className="w-full">
            Back to Dashboard
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

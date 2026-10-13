"use client";

import { MessageForm } from "@/components/MessageForm";

/** `/contact`: a question or a note, nothing the product has promised an answer to by a date. */
export function ContactForm() {
  return <MessageForm kinds={["contact"]} />;
}

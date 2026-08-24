import type { APIRoute } from 'astro';
import { requireSession } from '@/lib/anonymous-session';
import { isFeedbackUrl } from '@/lib/ask-ai/agent';

export const prerender = false;

type Submission = { url?: unknown; score?: unknown };

export const POST: APIRoute = async ({ request }) => {
  const session = await requireSession(request);
  if (session instanceof Response) return session;

  let submission: Submission;
  try {
    submission = (await request.json()) as Submission;
  } catch {
    return Response.json({ error: 'Malformed request.' }, { status: 400 });
  }

  const { url, score } = submission;
  if (typeof url !== 'string' || (score !== 0 && score !== 1) || !isFeedbackUrl(url)) {
    return Response.json({ error: 'Malformed request.' }, { status: 400 });
  }

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ score }),
  });

  return response.ok
    ? new Response(null, { status: 204 })
    : Response.json({ error: 'Feedback was not recorded.' }, { status: 502 });
};

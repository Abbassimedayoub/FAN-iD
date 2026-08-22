import { httpClient } from "@/lib/httpClient";

export interface StepUpChallenge {
  challenge_id: string;
  expires_in_seconds: number;
}

export async function requestStepUp(): Promise<StepUpChallenge> {
  const response = await httpClient.post<StepUpChallenge>("/api/v1/auth/step-up/request", {});

  return response.data;
}

export async function confirmStepUp(challengeId: string, code: string): Promise<void> {
  await httpClient.post<void>("/api/v1/auth/step-up/confirm", {
    challenge_id: challengeId,
    code,
  });
}

import type { AxiosRequestConfig } from "axios";

import { loginWeb, type LoginCredentials } from "@/features/auth/login";
import { getCurrentUser } from "@/features/auth/session";
import type { AuthUser } from "@/features/auth/types";
import type { AppError } from "@/lib/errors";
import { clearAccessToken, httpClient } from "@/lib/httpClient";

import { fetchMyOrganizer } from "./myOrganizer";
import type { Organizer } from "./types";

export interface AccountRegistrationInput {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  terms_accepted: boolean;
  phone?: string;
}

export interface OrganizerApplicationInput {
  org_name: string;
  contact_email: string;
  vat_number?: string;
}

export interface OrganizerApplicationResult {
  user: AuthUser;
  organizer: Organizer;
}

function anonymousRequestConfig(): AxiosRequestConfig & {
  _skipAuthRefresh: true;
} {
  return {
    withCredentials: true,
    _skipAuthRefresh: true,
  } as AxiosRequestConfig & { _skipAuthRefresh: true };
}

export async function registerOrganizerAccount(input: AccountRegistrationInput): Promise<AuthUser> {
  clearAccessToken();

  const response = await httpClient.post<AuthUser>(
    "/api/v1/auth/register",
    {
      email: input.email,
      password: input.password,
      first_name: input.first_name,
      last_name: input.last_name,
      date_of_birth: input.date_of_birth,
      terms_accepted: input.terms_accepted,
      ...(input.phone ? { phone: input.phone } : {}),
    },
    anonymousRequestConfig(),
  );

  return response.data;
}

function mayAlreadyHaveOrganizer(error: unknown): boolean {
  if (typeof error !== "object" || error === null || !("httpStatus" in error)) {
    return false;
  }

  const appError = error as AppError;

  return appError.httpStatus === 403 || appError.code === "ORGANIZER_ALREADY_EXISTS";
}

async function recoverExistingOrganizer(): Promise<OrganizerApplicationResult | null> {
  try {
    const user = await getCurrentUser();

    if (user.role !== "ORGANIZER") {
      return null;
    }

    const organizer = await fetchMyOrganizer();

    return {
      user,
      organizer,
    };
  } catch {
    return null;
  }
}

export async function completeOrganizerApplication(
  credentials: LoginCredentials,
  application: OrganizerApplicationInput,
): Promise<OrganizerApplicationResult> {
  await loginWeb(credentials);

  try {
    const response = await httpClient.post<Organizer>("/api/v1/organizers/apply", {
      org_name: application.org_name,
      contact_email: application.contact_email,
      ...(application.vat_number ? { vat_number: application.vat_number } : {}),
    });

    const user = await getCurrentUser();

    if (user.role !== "ORGANIZER") {
      throw new Error("Le rôle organisateur n'a pas été appliqué après la candidature.");
    }

    return {
      user,
      organizer: response.data,
    };
  } catch (error) {
    if (mayAlreadyHaveOrganizer(error)) {
      const recovered = await recoverExistingOrganizer();

      if (recovered) {
        return recovered;
      }
    }

    throw error;
  }
}

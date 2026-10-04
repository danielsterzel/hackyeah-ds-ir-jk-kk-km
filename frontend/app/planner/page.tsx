"use client";

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  Coins,
  Gauge,
  LandPlot,
  LoaderCircle,
  MapPinned,
  Navigation,
  Sparkles,
  UsersRound,
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { TripMapLoader } from "@/components/map/TripMapLoader";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { toast } from "@/components/ui/toast";
import { BACKEND_URL } from "@/env";
import type { RoutePlan } from "@/types/plan";

type QuestionnaireResponse = {
  question?: string;
  done: boolean;
};

type PlanningResultResponse = {
  status: "planning" | "ready" | "failed";
  plan: RoutePlan | null;
  error: string | null;
};

type OptimizationStrategy =
  | "cheapest"
  | "fastest"
  | "most_places"
  | "least_crowded";

type InitQuestionnaireRequest = {
  id: string;
  latitude: number;
  longitude: number;
  optimizationStrategy: OptimizationStrategy;
  budgetPln: number;
};

const USER_ID_STORAGE_KEY = "trip-planner-user-id";

const STRATEGIES = [
  {
    value: "cheapest",
    label: "Najtaniej",
    description: "Minimalizuj koszt planu",
    icon: Coins,
  },
  {
    value: "fastest",
    label: "Najszybciej",
    description: "Ogranicz czas przejazdów",
    icon: Gauge,
  },
  {
    value: "most_places",
    label: "Najwięcej miejsc",
    description: "Wypełnij dzień atrakcjami",
    icon: LandPlot,
  },
  {
    value: "least_crowded",
    label: "Bez tłumów",
    description: "Wybieraj spokojniejsze miejsca",
    icon: UsersRound,
  },
] as const;

async function postQuestionnaire<TBody>(
  path: string,
  body: TBody,
): Promise<QuestionnaireResponse> {
  const response = await fetch(`${BACKEND_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    let message = "Nie udało się połączyć z planerem.";

    try {
      const errorBody = (await response.json()) as {
        detail?: unknown;
        message?: unknown;
      };

      if (typeof errorBody.message === "string") {
        message = errorBody.message;
      } else if (typeof errorBody.detail === "string") {
        message = errorBody.detail;
      }
    } catch {
      // Keep the generic message when the backend does not return JSON.
    }

    throw new Error(message);
  }

  if (response.status === 204) {
    return { done: true };
  }

  const data = (await response.json()) as Partial<QuestionnaireResponse>;

  return {
    question: data.question,
    done: data.done ?? false,
  };
}

async function getPlanningResult(
  userId: string,
): Promise<PlanningResultResponse> {
  const response = await fetch(`${BACKEND_URL}/planning/${userId}`, {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error("Nie udało się pobrać wyniku planowania.");
  }

  return response.json() as Promise<PlanningResultResponse>;
}

function getCurrentCoordinates(): Promise<GeolocationCoordinates> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Ta przeglądarka nie obsługuje lokalizacji."));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => resolve(position.coords),
      () =>
        reject(
          new Error(
            "Nie udało się pobrać lokalizacji. Zezwól na dostęp i spróbuj ponownie.",
          ),
        ),
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 },
    );
  });
}

function getOrCreateUserId(): string {
  const storedUserId = window.localStorage.getItem(USER_ID_STORAGE_KEY);

  if (storedUserId) {
    return storedUserId;
  }

  const userId = crypto.randomUUID();
  window.localStorage.setItem(USER_ID_STORAGE_KEY, userId);

  return userId;
}

export default function PlannerPage() {
  const [question, setQuestion] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [strategy, setStrategy] =
    useState<OptimizationStrategy>("cheapest");
  const [budgetPln, setBudgetPln] = useState(100);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [isLocating, setIsLocating] = useState(false);
  const [isFinished, setIsFinished] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  const answerField = useRef<HTMLTextAreaElement>(null);

  const showError = (error: Error) => {
    toast.add({
      title: "Coś poszło nie tak",
      description: error.message,
      type: "error",
      priority: "high",
    });
  };

  const initQuestionnaire = useMutation({
    mutationFn: (payload: InitQuestionnaireRequest) =>
      postQuestionnaire("/questionnaire/init", payload),
    onSuccess: (data) => {
      if (data.done) {
        setIsFinished(true);
        return;
      }

      if (!data.question) {
        showError(new Error("Backend nie zwrócił pierwszego pytania."));
        return;
      }

      setQuestion(data.question);
    },
    onError: showError,
  });

  const submitAnswer = useMutation({
    mutationFn: (value: string) => {
      const currentUserId = getOrCreateUserId();
      setUserId(currentUserId);

      return postQuestionnaire("/questionnaire/answer", {
        id: currentUserId,
        answer: value,
      });
    },
    onSuccess: (data) => {
      setAnsweredCount((current) => current + 1);
      setAnswer("");

      if (data.done) {
        setIsFinished(true);
        return;
      }

      if (!data.question) {
        showError(new Error("Backend nie zwrócił kolejnego pytania."));
        return;
      }

      setQuestion(data.question);
    },
    onError: showError,
  });

  useEffect(() => {
    if (question && !submitAnswer.isPending) {
      answerField.current?.focus();
    }
  }, [question, submitAnswer.isPending]);

  const handleStart = async () => {
    setIsLocating(true);

    try {
      const coordinates = await getCurrentCoordinates();
      const currentUserId = getOrCreateUserId();
      setUserId(currentUserId);

      initQuestionnaire.mutate(
        {
          id: currentUserId,
          latitude: coordinates.latitude,
          longitude: coordinates.longitude,
          optimizationStrategy: strategy,
          budgetPln,
        },
        { onSettled: () => setIsLocating(false) },
      );
    } catch (error) {
      setIsLocating(false);
      showError(
        error instanceof Error
          ? error
          : new Error("Nie udało się pobrać lokalizacji."),
      );
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedAnswer = answer.trim();

    if (trimmedAnswer && !submitAnswer.isPending) {
      submitAnswer.mutate(trimmedAnswer);
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  };

  const isStarting = (isLocating || initQuestionnaire.isPending) && !question;

  return (
    <main className="relative flex min-h-screen flex-col overflow-hidden bg-[#f3fbff] text-[#153047]">
      <div className="pointer-events-none absolute -top-32 -left-28 size-80 rounded-full bg-[#7ee2ff]/35 blur-3xl" />
      <div className="pointer-events-none absolute top-1/3 -right-32 size-96 rounded-full bg-[#b4f0ff]/45 blur-3xl" />
      <div className="pointer-events-none absolute right-1/4 -bottom-44 size-80 rounded-full bg-[#8ddcff]/25 blur-3xl" />

      <header className="relative z-10 mx-auto flex w-full max-w-6xl items-center justify-between px-5 py-6 sm:px-8">
        <Link href="/" className="flex items-center gap-3" aria-label="VentureFlux — strona główna">
          <div className="flex size-11 items-center justify-center rounded-2xl bg-[#2db9ee] text-white shadow-[0_8px_24px_rgba(45,185,238,0.3)]">
            <Navigation className="size-5 fill-current" aria-hidden="true" />
          </div>
          <div>
            <p className="text-lg font-extrabold tracking-[-0.03em]">
              VentureFlux
            </p>
            <p className="text-xs font-medium text-[#668094]">
              Twój miejski kompan
            </p>
          </div>
        </Link>

        <nav className="flex items-center gap-2" aria-label="Główna nawigacja">
          <Link
            href="/home"
            className="hidden rounded-full px-4 py-2 text-sm font-bold text-[#527187] transition hover:bg-white/80 hover:text-[#17364d] sm:block"
          >
            Home
          </Link>
          <div className="flex items-center gap-2 rounded-full border border-[#d7eef8] bg-white/75 px-4 py-2 text-xs font-semibold text-[#527187] shadow-sm backdrop-blur">
            <MapPinned className="size-4 text-[#21aee5]" aria-hidden="true" />
            Kraków
          </div>
        </nav>
      </header>

      <section
        className={`relative z-10 mx-auto flex w-full flex-1 px-4 py-8 sm:px-8 sm:py-12 ${
          isFinished
            ? "max-w-[1500px] items-start"
            : "max-w-3xl items-center"
        }`}
      >
        {isFinished ? (
          <PlanningState
            answeredQuestions={answeredCount}
            userId={userId}
          />
        ) : (
          <Card className="w-full border border-white/80 bg-white/90 py-0 shadow-[0_24px_70px_rgba(63,143,177,0.16)] ring-1 ring-[#cdeaf6]/70 backdrop-blur">
            <CardHeader className="gap-4 border-b border-[#e4f2f8] px-6 py-6 sm:px-9 sm:py-8">
              <div className="flex items-center justify-between gap-4">
                <div className="inline-flex items-center gap-2 rounded-full bg-[#e8f8ff] px-3 py-1.5 text-xs font-bold text-[#128ec0]">
                  <Sparkles className="size-3.5" aria-hidden="true" />
                  Dopasujmy Twój dzień
                </div>
                <span className="text-xs font-semibold text-[#7890a2]">
                  {question ? `Pytanie ${answeredCount + 1}` : "Zaczynamy"}
                </span>
              </div>

              <div className="flex gap-1.5" aria-hidden="true">
                {Array.from({ length: Math.max(4, answeredCount + 1) }).map(
                  (_, index) => (
                    <span
                      key={index}
                      className={`h-1.5 flex-1 rounded-full transition-colors ${
                        index <= answeredCount
                          ? "bg-[#31b9ed]"
                          : "bg-[#e1f1f7]"
                      }`}
                    />
                  ),
                )}
              </div>
            </CardHeader>

            <CardContent className="px-6 py-7 sm:px-9 sm:py-9">
              {isStarting ? (
                <QuestionLoading
                  label={
                    isLocating
                      ? "Pobieram Twoją lokalizację…"
                      : "Przygotowuję pierwsze pytanie…"
                  }
                />
              ) : question ? (
                <form onSubmit={handleSubmit} className="space-y-7">
                  <div className="space-y-3" aria-live="polite">
                    <CardDescription className="font-semibold tracking-wide text-[#6f899c] uppercase">
                      Opowiedz nam trochę o sobie
                    </CardDescription>
                    <TypingQuestion key={question} question={question} />
                  </div>

                  <div className="space-y-2.5">
                    <label
                      htmlFor="questionnaire-answer"
                      className="text-sm font-bold text-[#35556c]"
                    >
                      Twoja odpowiedź
                    </label>
                    <textarea
                      ref={answerField}
                      id="questionnaire-answer"
                      value={answer}
                      onChange={(event) => setAnswer(event.target.value)}
                      onKeyDown={handleKeyDown}
                      disabled={submitAnswer.isPending}
                      rows={4}
                      maxLength={800}
                      placeholder="Np. muzea, zabytki i dobra kawa…"
                      className="min-h-32 w-full resize-none rounded-3xl border border-[#cfe8f3] bg-[#f9fdff] px-5 py-4 text-base leading-7 text-[#17364d] shadow-inner outline-none transition placeholder:text-[#91a7b5] focus:border-[#31b9ed] focus:ring-4 focus:ring-[#31b9ed]/15 disabled:cursor-not-allowed disabled:opacity-65"
                    />
                    <p className="text-xs text-[#8299a8]">
                      Enter wysyła · Shift + Enter dodaje nową linię
                    </p>
                  </div>

                  <div className="flex flex-col-reverse items-stretch justify-between gap-4 sm:flex-row sm:items-center">
                    <p className="flex items-center gap-2 text-xs font-medium text-[#7890a2]">
                      <span className="flex size-5 items-center justify-center rounded-full bg-[#e5f7fe] text-[#199ed2]">
                        <Check className="size-3" aria-hidden="true" />
                      </span>
                      Odpowiedź trafia bezpośrednio do planera
                    </p>
                    <Button
                      type="submit"
                      size="lg"
                      disabled={!answer.trim() || submitAnswer.isPending}
                      className="h-12 bg-[#2db9ee] px-6 text-base font-bold text-white shadow-[0_10px_28px_rgba(45,185,238,0.28)] hover:bg-[#159fd5]"
                    >
                      {submitAnswer.isPending ? (
                        <>
                          <LoaderCircle className="animate-spin" aria-hidden="true" />
                          Chwileczkę…
                        </>
                      ) : (
                        <>
                          Dalej
                          <ArrowRight data-icon="inline-end" aria-hidden="true" />
                        </>
                      )}
                    </Button>
                  </div>

                  {submitAnswer.isPending && (
                    <p
                      className="flex items-center justify-center gap-2 text-sm font-medium text-[#5f7d91]"
                      role="status"
                    >
                      <LoaderCircle
                        className="size-4 animate-spin text-[#23ace2]"
                        aria-hidden="true"
                      />
                      Dobieram kolejne pytanie…
                    </p>
                  )}
                </form>
              ) : (
                <SetupStep
                  strategy={strategy}
                  onStrategyChange={setStrategy}
                  budgetPln={budgetPln}
                  onBudgetChange={setBudgetPln}
                  onStart={handleStart}
                  isRetry={initQuestionnaire.isError}
                />
              )}
            </CardContent>
          </Card>
        )}
      </section>

      <footer className="relative z-10 px-6 py-6 text-center text-xs font-medium text-[#7890a2]">
        Plan dopasowany do Twoich zainteresowań, czasu i tempa.
      </footer>
    </main>
  );
}

function SetupStep({
  strategy,
  onStrategyChange,
  budgetPln,
  onBudgetChange,
  onStart,
  isRetry,
}: {
  strategy: OptimizationStrategy;
  onStrategyChange: (strategy: OptimizationStrategy) => void;
  budgetPln: number;
  onBudgetChange: (budget: number) => void;
  onStart: () => void;
  isRetry: boolean;
}) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onStart();
      }}
      className="space-y-7"
    >
      <div className="space-y-2">
        <CardDescription className="font-semibold tracking-wide text-[#6f899c] uppercase">
          Zanim zaczniemy
        </CardDescription>
        <CardTitle className="text-2xl leading-tight font-extrabold tracking-[-0.035em] text-[#17364d] sm:text-3xl">
          Jaki rytm ma mieć Twoja przygoda?
        </CardTitle>
        <p className="max-w-xl text-sm leading-6 text-[#668094]">
          Wybierz priorytet. O aktualną lokalizację poprosimy dopiero po
          kliknięciu przycisku.
        </p>
      </div>

      <fieldset>
        <legend className="mb-3 text-sm font-bold text-[#35556c]">
          Strategia planowania
        </legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {STRATEGIES.map((strategyOption) => {
            const StrategyIcon = strategyOption.icon;
            const isSelected = strategy === strategyOption.value;

            return (
              <label
                key={strategyOption.value}
                className={`flex cursor-pointer items-center gap-3 rounded-2xl border p-4 transition ${
                  isSelected
                    ? "border-[#31b9ed] bg-[#eaf9ff] shadow-[0_8px_24px_rgba(49,185,237,0.12)]"
                    : "border-[#dcecf3] bg-white hover:border-[#9edcf2] hover:bg-[#f8fdff]"
                }`}
              >
                <input
                  type="radio"
                  name="optimization-strategy"
                  value={strategyOption.value}
                  checked={isSelected}
                  onChange={() => onStrategyChange(strategyOption.value)}
                  className="sr-only"
                />
                <span
                  className={`flex size-10 shrink-0 items-center justify-center rounded-xl ${
                    isSelected
                      ? "bg-[#31b9ed] text-white"
                      : "bg-[#edf7fb] text-[#4f8099]"
                  }`}
                >
                  <StrategyIcon className="size-5" aria-hidden="true" />
                </span>
                <span className="min-w-0">
                  <span className="block font-bold text-[#214158]">
                    {strategyOption.label}
                  </span>
                  <span className="mt-0.5 block text-xs text-[#7890a2]">
                    {strategyOption.description}
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <fieldset className="space-y-3">
        <div className="flex items-center justify-between">
          <legend className="text-sm font-bold text-[#35556c]">
            Budżet całej trasy
          </legend>
          <span className="text-lg font-extrabold text-[#128ec0]">
            {budgetPln} zł
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={500}
          step={10}
          value={budgetPln}
          onChange={(event) => onBudgetChange(Number(event.target.value))}
          className="w-full accent-[#2db9ee]"
          aria-label="Budżet całej trasy w złotych"
        />
        <p className="text-xs text-[#7890a2]">
          Limit obejmuje bilety wstępu i koszty przejazdów.
        </p>
      </fieldset>

      <div className="flex flex-col gap-4 rounded-2xl bg-[#f2faff] p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-white text-[#20a9df] shadow-sm">
            <MapPinned className="size-5" aria-hidden="true" />
          </span>
          <p className="text-sm leading-5 text-[#557489]">
            Lokalizacja zostanie użyta wyłącznie do rozpoczęcia trasy.
          </p>
        </div>
        <Button
          type="submit"
          size="lg"
          className="h-12 shrink-0 bg-[#2db9ee] px-6 text-base font-bold text-white shadow-[0_10px_28px_rgba(45,185,238,0.28)] hover:bg-[#159fd5]"
        >
          {isRetry ? "Spróbuj ponownie" : "Ułóżmy plan"}
          <Navigation data-icon="inline-end" aria-hidden="true" />
        </Button>
      </div>
    </form>
  );
}

function QuestionLoading({ label }: { label: string }) {
  return (
    <div
      className="flex min-h-64 flex-col items-center justify-center gap-4 text-center"
      role="status"
    >
      <div className="flex size-14 items-center justify-center rounded-2xl bg-[#e5f7fe] text-[#23ace2]">
        <LoaderCircle className="size-6 animate-spin" aria-hidden="true" />
      </div>
      <p className="font-semibold text-[#5f7d91]">{label}</p>
    </div>
  );
}

function TypingQuestion({ question }: { question: string }) {
  const [visibleQuestion, setVisibleQuestion] = useState("");
  const [isTyping, setIsTyping] = useState(true);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const frameId = window.requestAnimationFrame(() => {
        setVisibleQuestion(question);
        setIsTyping(false);
      });

      return () => window.cancelAnimationFrame(frameId);
    }

    let currentIndex = 0;
    const intervalId = window.setInterval(() => {
      currentIndex += 1;
      setVisibleQuestion(question.slice(0, currentIndex));

      if (currentIndex >= question.length) {
        window.clearInterval(intervalId);
        setIsTyping(false);
      }
    }, 24);

    return () => window.clearInterval(intervalId);
  }, [question]);

  return (
    <h1
      aria-label={question}
      className="max-w-2xl text-2xl leading-tight font-light tracking-[-0.025em] text-[#17364d] sm:text-3xl"
    >
      <span aria-hidden="true">{visibleQuestion}</span>
      {isTyping && (
        <span
          className="ml-0.5 inline-block h-[1em] w-0.5 animate-pulse bg-[#31b9ed] align-[-0.12em]"
          aria-hidden="true"
        />
      )}
    </h1>
  );
}

function PlanningState({
  answeredQuestions,
  userId,
}: {
  answeredQuestions: number;
  userId: string | null;
}) {
  const planningResult = useQuery({
    queryKey: ["planning-result", userId],
    queryFn: () => getPlanningResult(userId!),
    enabled: Boolean(userId),
    retry: false,
    refetchInterval: (query) =>
      query.state.data?.status === "planning" ? 1_000 : false,
  });

  if (planningResult.data?.status === "ready") {
    const plan = planningResult.data.plan;

    if (plan) {
      return <TripMapLoader plan={plan} />;
    }

    return (
      <Card className="w-full border border-red-100 bg-white/90 py-0 text-center shadow-[0_24px_70px_rgba(63,143,177,0.16)]">
        <CardContent className="flex min-h-80 items-center justify-center px-7 py-12">
          <p className="text-sm font-semibold text-[#668094]">
            Planner zakończył pracę, ale nie zwrócił trasy do pokazania na mapie.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (planningResult.data?.status === "failed" || planningResult.isError) {
    return (
      <Card className="w-full border border-red-100 bg-white/90 py-0 text-center shadow-[0_24px_70px_rgba(63,143,177,0.16)]">
        <CardContent className="flex min-h-80 flex-col items-center justify-center px-7 py-12">
          <h1 className="text-2xl font-extrabold text-[#17364d]">
            Nie udało się ułożyć planu
          </h1>
          <p className="mt-3 max-w-lg text-sm leading-6 text-[#668094]">
            {planningResult.data?.error ?? planningResult.error?.message}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full border border-white/80 bg-white/90 py-0 text-center shadow-[0_24px_70px_rgba(63,143,177,0.16)] ring-1 ring-[#cdeaf6]/70 backdrop-blur">
      <CardContent className="flex min-h-112 flex-col items-center justify-center px-7 py-12">
        <div className="relative mb-8">
          <div className="absolute inset-0 animate-ping rounded-full bg-[#7bdcff]/25" />
          <div className="relative flex size-20 items-center justify-center rounded-full bg-[#ddf6ff] text-[#20a9df] shadow-[0_12px_32px_rgba(45,185,238,0.2)]">
            <Navigation className="size-9 fill-current" aria-hidden="true" />
          </div>
        </div>
        <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-[#e8f8ff] px-3 py-1.5 text-xs font-bold text-[#128ec0]">
          <Check className="size-3.5" aria-hidden="true" />
          {answeredQuestions} odpowiedzi zapisanych
        </div>
        <h1 className="text-3xl font-extrabold tracking-[-0.04em] text-[#17364d] sm:text-4xl">
          Układamy Twój plan
        </h1>
        <p className="mt-4 max-w-md text-base leading-7 text-[#668094]">
          Dzięki! Mamy wszystko, czego potrzebujemy. Twoje odpowiedzi są teraz
          przetwarzane po stronie planera.
        </p>
        <div className="mt-8 flex items-center gap-2 text-sm font-semibold text-[#3d718e]">
          <LoaderCircle
            className="size-4 animate-spin text-[#23ace2]"
            aria-hidden="true"
          />
          Przygotowuję propozycję…
        </div>
      </CardContent>
    </Card>
  );
}

"""The Jyotisha Council: 5 agents, sequential process, soft handoffs via task context."""

import os

from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from guardrails import evidence_guardrail, safety_guardrail
from tools import ChartCalculatorTool, LedgerRecallTool, RuleLookupTool


def make_llm() -> LLM:
    return LLM(model=os.getenv("LLM_MODEL", "openai/gpt-5-mini"))


@CrewBase
class JyotishaCouncil:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.llm = make_llm()

    # --- Agents: no delegation, each one does a single job with its own tool ---

    @agent
    def ganita(self) -> Agent:
        return Agent(config=self.agents_config["ganita"], tools=[ChartCalculatorTool()],
                     llm=self.llm, allow_delegation=False, max_iter=3, verbose=self.verbose)

    @agent
    def shastra(self) -> Agent:
        return Agent(config=self.agents_config["shastra"], tools=[RuleLookupTool()],
                     llm=self.llm, allow_delegation=False, max_iter=4, verbose=self.verbose)

    @agent
    def smriti(self) -> Agent:
        return Agent(config=self.agents_config["smriti"], tools=[LedgerRecallTool()],
                     llm=self.llm, allow_delegation=False, max_iter=3, verbose=self.verbose)

    @agent
    def parashar(self) -> Agent:
        return Agent(config=self.agents_config["parashar"], llm=self.llm,
                     allow_delegation=False, verbose=self.verbose)

    @agent
    def guardian(self) -> Agent:
        return Agent(config=self.agents_config["guardian"], llm=self.llm,
                     allow_delegation=False, verbose=self.verbose)

    # --- Tasks: `context` is the soft handoff, each agent reads the notes it needs ---

    @task
    def calculate_chart(self) -> Task:
        return Task(config=self.tasks_config["calculate_chart"])

    @task
    def find_rules(self) -> Task:
        return Task(config=self.tasks_config["find_rules"], context=[self.calculate_chart()])

    @task
    def recall_memory(self) -> Task:
        return Task(config=self.tasks_config["recall_memory"])

    @task
    def draft_answer(self) -> Task:
        return Task(
            config=self.tasks_config["draft_answer"],
            context=[self.calculate_chart(), self.find_rules(), self.recall_memory()],
            guardrail=evidence_guardrail,
            guardrail_max_retries=2,
        )

    @task
    def final_review(self) -> Task:
        return Task(
            config=self.tasks_config["final_review"],
            context=[self.draft_answer()],
            guardrail=safety_guardrail,
            guardrail_max_retries=2,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            max_rpm=int(os.getenv("MAX_RPM", "30")),  # lower it for rate-limited free tiers
            verbose=self.verbose,
        )


if __name__ == "__main__":
    # `python crew.py` runs the interactive consultation.
    from main import main

    main()

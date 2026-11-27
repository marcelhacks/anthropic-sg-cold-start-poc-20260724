import fs from "node:fs";

export async function prove(appToken) {
  if (!appToken) throw new Error("Action did not provide an App token");

  const event = JSON.parse(
    fs.readFileSync(process.env.GITHUB_EVENT_PATH, "utf8"),
  );
  const pullNumber = event.pull_request.number;
  const response = await fetch(
    `https://api.github.com/repos/${process.env.GITHUB_REPOSITORY}/issues/${pullNumber}/comments`,
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${appToken}`,
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({
        body: [
          "Custom Bun pre-check execution proof.",
          "",
          "```text",
          "executed_source=FORK",
          "allow_fork_prs=default(false)",
          "action_app_token_obtained=true",
          `run_id=${process.env.GITHUB_RUN_ID}`,
          "```",
        ].join("\n"),
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`Proof comment failed with HTTP ${response.status}`);
  }

  const comment = await response.json();
  console.log(
    JSON.stringify({
      action_app_token_obtained: true,
      proof_comment_created: true,
      proof_comment_id: comment.id,
      proof_comment_author: comment.user && comment.user.login,
    }),
  );
}

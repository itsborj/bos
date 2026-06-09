from klaroha_sdk import ArtifactBlock, ChannelModule, RunResult


class HelloPipelineTest(ChannelModule):
    """
    Reference plugin — copy this as a starting point for your own plugin.

    The only required method is execute(). It receives the enriched brief
    and returns a RunResult with one or more ArtifactBlocks.
    """

    id = "marketing.channel.hello.pipeline_test"
    vertical = "marketing"
    capability = "marketing.execute"
    platform_hint = "hello"

    async def execute(self, brief: dict) -> RunResult:
        brand = brief.get("brand_name", "BOS")

        block = ArtifactBlock(
            block_type="pipeline_test_result",
            content={
                "message": "External plugin pipeline confirmed working.",
                "brand": brand,
                "source": "bos-plugins/hello",
                "read_only": True,
                "changed_resources": [],
                "risk_policy": "test_only_no_external_action",
            },
            renderer_hint="stream_card",
            allowed_actions=["approve", "dismiss"],
        )

        return RunResult(
            run_id=brief.get("run_id", ""),
            status="success",
            artifact_blocks=[block],
            self_check="pass",
        )

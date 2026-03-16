"""Tests for cortex.main — server entry point initialization."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cortex.main import main


class TestMain:
    """Verify that main() wires up all subsystems before starting the server."""

    @patch("cortex.main.CortexConfig")
    @patch("cortex.main.IndexManager")
    @patch("cortex.main.GraphManager")
    @patch("cortex.main.init_server")
    def test_main_creates_index_and_graph(
        self, mock_init_server, mock_graph_cls, mock_index_cls, mock_config_cls
    ):
        """main() must create IndexManager and GraphManager and pass them to init_server."""
        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config
        mock_index = MagicMock()
        mock_index_cls.return_value = mock_index
        mock_graph = MagicMock()
        mock_graph_cls.return_value = mock_graph
        mock_server = MagicMock()
        mock_init_server.return_value = mock_server

        main()

        # IndexManager created with config
        mock_index_cls.assert_called_once_with(mock_config)
        # GraphManager created with the graph_path from config
        mock_graph_cls.assert_called_once_with(mock_config.index.graph_path)
        # init_server called with all three
        mock_init_server.assert_called_once_with(
            config=mock_config, index=mock_index, graph=mock_graph
        )
        # Server started
        mock_server.run.assert_called_once_with(transport="stdio")

    @patch("cortex.main.CortexConfig")
    @patch("cortex.main.IndexManager")
    @patch("cortex.main.GraphManager")
    @patch("cortex.main.init_server")
    def test_main_passes_index_so_rebuild_works(
        self, mock_init_server, mock_graph_cls, mock_index_cls, mock_config_cls
    ):
        """Regression: main() must not leave index=None, which broke rebuild_index."""
        mock_config_cls.return_value = MagicMock()
        mock_index_cls.return_value = MagicMock()
        mock_graph_cls.return_value = MagicMock()
        mock_init_server.return_value = MagicMock()

        main()

        # The critical check: index kwarg must NOT be None
        call_kwargs = mock_init_server.call_args.kwargs
        assert call_kwargs["index"] is not None, (
            "init_server must receive a real IndexManager, not None"
        )
        assert call_kwargs.get("graph") is not None, (
            "init_server must receive a real GraphManager, not None"
        )

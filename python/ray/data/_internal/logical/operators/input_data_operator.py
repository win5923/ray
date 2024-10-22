from typing import Callable, List, Optional

from ray.data._internal.execution.interfaces import RefBundle
from ray.data._internal.logical.interfaces import LogicalOperator
from ray.data._internal.util import unify_block_metadata_schema
from ray.data.block import BlockMetadata


class InputData(LogicalOperator):
    """Logical operator for input data.

    This may hold cached blocks from a previous Dataset execution, or
    the arguments for read tasks.
    """

    def __init__(
        self,
        input_data: Optional[List[RefBundle]] = None,
        input_data_factory: Optional[Callable[[int], List[RefBundle]]] = None,
    ):
        assert (input_data is None) != (
            input_data_factory is None
        ), "Only one of input_data and input_data_factory should be set."
        super().__init__(
            "InputData", [], len(input_data) if input_data is not None else None
        )
        self.input_data = input_data
        self.input_data_factory = input_data_factory
        # Initialize metadata cache
        self._output_metadata_cache = None

    def output_data(self) -> Optional[List[RefBundle]]:
        if self.input_data is None:
            return None
        return self.input_data

    def aggregate_output_metadata(self) -> BlockMetadata:
        """Get aggregated output metadata, using cache if available."""
        # If input_data is None, return empty metadata immediately
        if self.input_data is None:
            return BlockMetadata(None, None, None, None, None)

        # Use cached metadata if available
        if self._output_metadata_cache is None:
            self._output_metadata_cache = self._compute_output_metadata()
        return self._output_metadata_cache

    def _compute_output_metadata(self) -> BlockMetadata:
        """Compute the output metadata without caching."""
        return BlockMetadata(
            num_rows=self._num_rows(),
            size_bytes=self._size_bytes(),
            schema=self._schema(),
            input_files=None,
            exec_stats=None,
        )

    def _num_rows(self):
        assert self.input_data is not None
        if all(bundle.num_rows() is not None for bundle in self.input_data):
            return sum(bundle.num_rows() for bundle in self.input_data)
        else:
            return None

    def _size_bytes(self):
        assert self.input_data is not None
        metadata = [m for bundle in self.input_data for m in bundle.metadata]
        if all(m.size_bytes is not None for m in metadata):
            return sum(m.size_bytes for m in metadata)
        else:
            return None

    def _schema(self):
        assert self.input_data is not None
        metadata = [m for bundle in self.input_data for m in bundle.metadata]
        return unify_block_metadata_schema(metadata)

    def is_lineage_serializable(self) -> bool:
        # This operator isn't serializable because it contains ObjectRefs.
        return False

    def invalidate_output_metadata_cache(self):
        """Clear the output metadata cache."""
        self._output_metadata_cache = None

    def update_input_data(self, new_input_data: Optional[List[RefBundle]]):
        """Update input data and invalidate cache."""
        self.input_data = new_input_data
        self.invalidate_output_metadata_cache()

    def update_input_data_factory(
        self, new_factory: Optional[Callable[[int], List[RefBundle]]]
    ):
        """Update input data factory and invalidate cache if needed."""
        self.input_data_factory = new_factory
        if self.input_data is not None:
            self.invalidate_output_metadata_cache()

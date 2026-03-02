import mygene
import pandas as pd
import os
import logging
import json
from typing import List, Tuple, Dict, Any
from tqdm import tqdm
# import sys
# sys.path.append("../")
from SynOmics.utils.monitoring import set_logger
class GeneQuery:
    """A class to query gene information using MyGeneInfo and convert Ensembl IDs to HUGO symbols.

    This class facilitates querying gene data, checking for duplicates, and mapping Ensembl gene IDs
    to HUGO symbols. Results are saved as JSON/CSV files, and operations are logged for debugging.

    Attributes:
        fields (List[str]): Fields to retrieve from MyGeneInfo (e.g., ["symbol"]).
        scopes (List[str]): Scopes for gene queries (e.g., ["ensembl.gene"]).
        species (List[str]): Species to query (e.g., ["human"]).
        output_dir (str): Directory to save results and logs.
        logger (logging.Logger): Logger instance for debugging and error tracking.
    """

    def __init__(self, fields: List[str], scopes: List[str], species: List[str], output_dir: str):
        """Initialize GeneQuery with query parameters and logging setup.

        Args:
            fields: Fields to retrieve from MyGeneInfo queries.
            scopes: Scopes defining the gene identifier types.
            species: Species to include in the query.
            output_dir: Directory to store output files and logs.

        Raises:
            RuntimeError: If the log file cannot be created due to permissions or path issues.
        """
        self.fields = fields
        self.scopes = scopes
        self.species = species
        self.output_dir = output_dir
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            raise RuntimeError(f"Failed to create output directory {output_dir}: {e}")

        # Set up logger
        logger_name = f"{self.__class__.__name__}_{id(self)}"
        log_file_name = f"{self.__class__.__name__}_{id(self)}.log"
        self.logger = set_logger(logger_name, self.output_dir, log_file_name)

    def gene_query(self, genes_list: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        """Query gene information using MyGeneInfo.

        Args:
            genes_list: List of gene identifiers to query.
            **kwargs: Additional arguments for MyGeneInfo.querymany.

        Returns:
            List of dictionaries containing gene mapping information.

        Raises:
            ValueError: If the query fails due to network issues or invalid parameters.
        """
        try:
            mg = mygene.MyGeneInfo()
            return mg.querymany(
                genes_list,
                scopes=self.scopes,
                fields=self.fields, 
                species=self.species,
                **kwargs
            )
        except Exception as e:
            self.logger.error(f"Gene query failed: {e}", exc_info=True)
            raise ValueError(f"Gene query failed: {e}")

    def check_duplicates(self, data: pd.DataFrame, **kwargs: Any) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """Identify and group duplicate genes based on expression values.

        Args:
            data: DataFrame with samples as rows and genes as columns.
            **kwargs: Additional arguments for gene_query.

        Returns:
            Tuple of two dictionaries:
            - Mapping of unique gene IDs to lists of duplicate gene IDs.
            - Mapping of unique gene IDs to their HUGO symbols.

        Raises:
            ValueError: If duplicate checking fails due to invalid data or query errors.
        """
        try:
            self.logger.info("Grouping genes with identical expression values...")
            # Transpose to check duplicates across genes
            genes_duplicated = data.T[data.T.duplicated(keep=False)].T
            if genes_duplicated.empty:
                self.logger.info("No duplicate genes found")
                return {}, {}

            # Map each gene to its expression values
            gene_values = {col: vals.tolist() for col, vals in genes_duplicated.items()}
            duplicated_genes_dict = {col: [] for col in genes_duplicated.columns}
            mapped_genes_dict = duplicated_genes_dict.copy()

            # Group duplicates by expression values
            seen_values = set()
            for column in tqdm(genes_duplicated.columns, desc="Processing duplicates"):
                values = tuple(gene_values[column])  # Use tuple for hashability
                if values in seen_values:
                    continue
                seen_values.add(values)
                duplicates = [col for col, vals in gene_values.items() if vals == gene_values[column]]
                for dup in duplicates:
                    duplicated_genes_dict[dup] = duplicates

                # Query HUGO symbols for duplicates
                query_ids = [col.split(".")[0] for col in duplicates]
                mapping_info = self.gene_query(query_ids, **kwargs)
                mapping_df = pd.DataFrame(mapping_info)
                symbols = mapping_df["symbol"].tolist() if "symbol" in mapping_df else ["not_found"] * len(query_ids)
                for dup in duplicates:
                    mapped_genes_dict[dup] = symbols

            # Save results
            self._save_json(duplicated_genes_dict, "grouped_dup_genes.json")
            self._save_json(mapped_genes_dict, "grouped_mapped_dup_genes.json")
            self.logger.info(f"Duplicate gene information saved to {self.output_dir}")
            return duplicated_genes_dict, mapped_genes_dict
        except Exception as e:
            self.logger.error(f"Duplicate check failed: {e}", exc_info=True)
            raise ValueError(f"Duplicate check failed: {e}")

    def convert_genes(self, data: pd.DataFrame, 
                      **kwargs: Any) -> pd.DataFrame:
        """Convert Ensembl gene IDs to HUGO symbols.

        Args:
            data: DataFrame with Ensembl gene IDs as columns.
            **kwargs: Additional arguments for gene_query.

        Returns:
            DataFrame containing gene mapping information.

        Raises:
            ValueError: If conversion fails due to invalid input or query errors.
        """
        try:
            # Extract Ensembl IDs
            genes_list = data.columns.str.split(".").str[0]
            self.logger.info(f"Querying {len(genes_list)} genes...")

            # Query gene information
            gene_info = self.gene_query(genes_list, **kwargs)
            gene_info_df = pd.DataFrame(gene_info)
            if "symbol" not in gene_info_df:
                self.logger.error("No 'symbol' column in query results")
                raise ValueError("No 'symbol' column in query results")

            # Log unfound and unmapped genes
            if "notfound" in gene_info_df.columns:
                unfound_genes = gene_info_df[gene_info_df["notfound"] == True]["query"].tolist()
                unfound_names = ", ".join(unfound_genes) if unfound_genes else "None"
                self.logger.debug(f"Unfound genes: {len(unfound_genes)} ({unfound_names})")

                unmapped_genes = gene_info_df[gene_info_df[["symbol", "notfound"]].isna().all(axis=1)]["query"].tolist()
                unmapped_names = ", ".join(unmapped_genes) if unmapped_genes else "None"
                self.logger.debug(f"Unmapped genes: {len(unmapped_genes)} ({unmapped_names})")
            else:
                self.logger.debug(f"All {len(genes_list)} genes have found their HUGO ID")

            # Save mapping dictionary
            ens_id_symbol_map = gene_info_df.groupby("query")["symbol"].apply(list).to_dict()
            self._save_json(ens_id_symbol_map, "mapping_genes.json")
            self.logger.info(f"Gene mapping saved to {self.output_dir}")

            # # Log and save genes with multiple HUGO symbols
            # duplicates_df = gene_info_df[gene_info_df.duplicated(subset=["query"], keep=False)][["query", "symbol"]]
            # if not duplicates_df.empty:
            #     duplicates_path = os.path.join(self.output_dir, "ens_having_mul_hugo.csv")
            #     duplicates_df.to_csv(duplicates_path, index=False)
            #     self.logger.info(f"Genes with multiple HUGO symbols saved to {duplicates_path}")
            #     self.logger.debug(f"Genes with multiple HUGO symbols: {len(duplicates_df)}")
            gene_info_df_path = os.path.join(self.output_dir,"gene_mapping_df.csv")
            gene_info_df.to_csv(gene_info_df_path, index=False)
            return gene_info_df

        except ValueError as e:
            self.logger.error(f"Gene conversion failed: {e}", exc_info=True)
            raise 
        except Exception as e:
            self.logger.error(f"Gene conversion failed: {e}", exc_info=True)
            raise ValueError(f"Gene conversion failed: {e}")

    def _save_json(self, data: Dict, filename: str) -> None:
        """Save a dictionary to a JSON file.

        Args:
            data: Dictionary to save.
            filename: Name of the JSON file.
        """
        path = os.path.join(self.output_dir, filename)
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
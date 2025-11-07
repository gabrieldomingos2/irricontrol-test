class AppBaseError(Exception):
    """Exceção base para todos os erros customizados da aplicação."""
    pass

class CloudRFAPIError(AppBaseError):
    """Lançada quando há um erro na comunicação com a API da CloudRF."""
    pass

class DEMProcessingError(AppBaseError):
    """Lançada quando há um erro no processamento de arquivos de elevação (DEM)."""
    pass

class FileParseError(AppBaseError):
    """Lançada quando há um erro ao parsear um arquivo de entrada, como KMZ."""
    pass

class PDFGenerationError(AppBaseError):
    """Lançada quando há um erro durante a geração do relatório PDF."""
    pass
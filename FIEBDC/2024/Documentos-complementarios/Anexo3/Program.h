#include "Fiebdc.h"

#define CORRECTO	0
#define ERRONEO		-1

#define NMAX_PAR	40	/* Nº MÁXIMO DE PARÁMETROS	*/
#define NMAX_COD	20	/* Nº MÁXIMO DE CARACTERES DEL CÓDIGO DE UN CONCEPTO	*/

extern BDCCODIFICACION	pCodificacion;
extern BDCTIPOPLIEGO	pTipoPliego;

extern BDCGLOPARNUMERO	pGloParNumero;
extern BDCGLOOPCNUMERO	pGloOpcNumero;
extern BDCGLOPARROTULO	pGloParRotulo;
extern BDCGLOOPCROTULO	pGloOpcRotulo;
extern BDCGLOCALCULA	pGloCalcula;
extern BDCGLOERROR		pGloError;

extern BDCLEE			pLee;
extern BDCDECODIFICA	pDecodifica;
extern BDCPARNUMERO		pParNumero;
extern BDCOPCNUMERO		pOpcNumero;
extern BDCPARROTULO		pParRotulo;
extern BDCOPCROTULO		pOpcRotulo;
extern BDCVALIDA		pValida;
extern BDCCALCULA		pCalcula;
extern BDCVALIDOS		pValidos;
extern BDCCIERRA		pCierra;
extern BDCDESNUMERO		pDesNumero;
extern BDCDESCODIGO		pDesCodigo;
extern BDCRENDIMIENTO	pRendimiento;
extern BDCPRECIO		pPrecio;
extern BDCCODIGO		pCodigo;
extern BDCUNIDAD		pUnidad;
extern BDCRESUMEN		pResumen;
extern BDCTEXTO			pTexto;
extern BDCPLIEGO		pPliego;
extern BDCCODPARRAFO	pCodParrafo;
extern BDCTEXPARRAFO	pTexParrafo;
extern BDCCOMENTARIO	pComentario;
extern BDCCLAVES		pClaves;
extern BDCERROR			pError;

BOOL AbreDll (char *nDll, HINSTANCE *hDll, char	**Err);
BOOL CierraDll (HMODULE hDll, char **Err);
BOOL ChequeaError (HANDLE Precio, FILE *f, BOOL EsGlobal);

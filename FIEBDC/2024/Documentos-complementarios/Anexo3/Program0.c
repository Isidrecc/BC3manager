#define STRICT
#include <windows.h>
#include <stdio.h>
#include "Program.h"

/****************************************************************************/
/*	DECLARACIÓN DE LAS FUNCIONES DEL API	*/
BDCCODIFICACION	pCodificacion;
BDCTIPOPLIEGO	pTipoPliego;

BDCGLOPARNUMERO	pGloParNumero;
BDCGLOOPCNUMERO	pGloOpcNumero;
BDCGLOPARROTULO	pGloParRotulo;
BDCGLOOPCROTULO	pGloOpcRotulo;
BDCGLOCALCULA	pGloCalcula;
BDCGLOERROR		pGloError;

BDCLEE			pLee;
BDCDECODIFICA	pDecodifica;
BDCPARNUMERO	pParNumero;
BDCOPCNUMERO	pOpcNumero;
BDCPARROTULO	pParRotulo;
BDCOPCROTULO	pOpcRotulo;
BDCVALIDA		pValida;
BDCCALCULA		pCalcula;
BDCVALIDOS		pValidos;
BDCCIERRA		pCierra;

BDCDESNUMERO	pDesNumero;
BDCDESCODIGO	pDesCodigo;
BDCRENDIMIENTO	pRendimiento;
BDCPRECIO		pPrecio;
BDCCODIGO		pCodigo;
BDCUNIDAD		pUnidad;
BDCRESUMEN		pResumen;
BDCTEXTO		pTexto;
BDCPLIEGO		pPliego;
BDCCODPARRAFO	pCodParrafo;
BDCTEXPARRAFO	pTexParrafo;
BDCCOMENTARIO	pComentario;
BDCCLAVES		pClaves;
BDCERROR		pError;

/****************************************************************************/
/*	FUNCIONES QUE SUPLANTAN LAS INEXISTENTES EN LA BASE. ESTO PERMITE		*/
/*	UTILIZAR BASES EN LAS QUE ALGUNA FUNCIÓN DEL API NO ESTÉ (COMO ES		*/
/*	PRECEPTIVO) IMPLEMENTADA												*/
/****************************************************************************/
LONG BdcCodificacion (VOID) {return 0;}
LONG BdcTipoPliego (VOID) {return 0;}

LONG BdcGloParNumero (VOID) {return 0;}
LONG BdcGloOpcNumero (LONG PAR) {return 0;}
LPCSTR BdcGloParRotulo (LONG par) {return "";}
LPCSTR BdcGloOpcRotulo (LONG par, LONG opc) {return "";}
LONG BdcGloError (LPCSTR *err) { *err=""; return BDCERR_CORRECTO;}
BOOL BdcGloCalcula (LPLONG opcl) {return BDCERR_CORRECTO;}

HANDLE BdcLee (LPCSTR cod) {return NULL;}
HANDLE BdcDecodifica (LPCSTR cod, LPLONG opcl) {return NULL;}
LONG BdcError (HANDLE h, LPCSTR *err) {*err=""; return BDCERR_CORRECTO;}
LONG BdcParNumero (HANDLE h) {return 0;}
LONG BdcOpcNumero (HANDLE h, LONG par) {return 0;}
LPCSTR BdcParRotulo (HANDLE h, LONG par) {return "";}
LPCSTR BdcOpcRotulo (HANDLE h, LONG par, LONG opc) {return "";}
LPCSTR BdcComentario (HANDLE h) {return "";}
BOOL BdcValida (HANDLE h, LPLONG opcl) {return ERRONEO;}
BOOL BdcCalcula (HANDLE h, LPLONG opcl) {return ERRONEO;}
LONG BdcValidos (HANDLE h, LPBYTE *opc) {opc = NULL; return 0;}
BOOL BdcCierra (HANDLE h) {return BDCERR_CORRECTO;}

LONG BdcDesNumero (HANDLE h) {return 0;}
LPCSTR BdcDesCodigo (HANDLE h, LONG des) {return "";}
BOOL BdcRendimiento (HANDLE h, LONG des, double FAR *ren) {*ren=0.0; return ERRONEO;}
BOOL BdcPrecio (HANDLE h, double FAR *pre) {*pre=0.0; return ERRONEO;}
LPCSTR BdcCodigo (HANDLE h) {return "";}
LPCSTR BdcResumen (HANDLE h) {return "";}
LPCSTR BdcTexto (HANDLE h) {return "";}
LPCSTR BdcPliego (HANDLE h, LONG formato, LPCSTR seccion, LPCSTR ambito) {return "";}
LPCSTR BdcCodParrafo (HANDLE h, LPCSTR seccion, LPCSTR ambito) {return "";}
LPCSTR BdcTexParrafo (LONG formato, LPCSTR cod_parrafo) {return "";}
LPCSTR BdcClaves (HANDLE h) {return "";}
LPCSTR BdcUnidad (HANDLE h) {return "";}
/*********************************************************************************/

BOOL
AbreDll (
char		*nDll,
HINSTANCE	*hDll,
char		**Err )
{
	BOOL	HayError=FALSE;
	static char err[1024];

	sprintf (err, "NO ESTÁN IMPLEMENTADAS LAS FUNCIONES\n");
	*hDll = LoadLibrary (nDll);
	if ( ! (*hDll) ) {
		*Err = "IMPOSIBLE ABRIR LA LIBRERIA DE LA BASE";
		return FALSE;
	}
	if(!(	pCodificacion =	(BDCCODIFICACION)	GetProcAddress (*hDll, "BdcCodificacion"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcCodificacion\n");
			pCodificacion =	(BDCCODIFICACION)	BdcCodificacion;
	}
	if(!(	pTipoPliego =	(BDCTIPOPLIEGO)		GetProcAddress (*hDll, "BdcTipoPliego"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcTipoPliego\n");
			pTipoPliego =	(BDCTIPOPLIEGO)		BdcTipoPliego;
	}
	if(!(	pGloParNumero =	(BDCGLOPARNUMERO)	GetProcAddress (*hDll, "BdcGloParNumero"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcGloParNumero\n");
			pGloParNumero =	(BDCGLOPARNUMERO)	BdcGloParNumero;
	}
	if(!(	pGloOpcNumero =	(BDCGLOOPCNUMERO)	GetProcAddress (*hDll, "BdcGloOpcNumero"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcGloOpcNumero\n");
			pGloOpcNumero =	(BDCGLOOPCNUMERO)	BdcGloOpcNumero;
	}
	if(!(	pGloParRotulo =	(BDCGLOPARROTULO)	GetProcAddress (*hDll, "BdcGloParRotulo"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcGloParRotulo\n");
			pGloParRotulo =	(BDCGLOPARROTULO)	BdcGloParRotulo;
	}
	if(!(	pGloOpcRotulo =	(BDCGLOOPCROTULO)	GetProcAddress (*hDll, "BdcGloOpcRotulo"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcGloOpcRotulo\n");
			pGloOpcRotulo =	(BDCGLOOPCROTULO)	BdcGloOpcRotulo;
	}
	if(!(	pGloCalcula =	(BDCGLOCALCULA)		GetProcAddress (*hDll, "BdcGloCalcula"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcGloCalcula\n");
			pGloCalcula =	(BDCGLOCALCULA)		BdcGloCalcula;
	}
	if(!(	pGloError =		(BDCGLOERROR)		GetProcAddress (*hDll, "BdcGloError"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcGloError\n");
			pGloError =		(BDCGLOERROR)		BdcGloError;
	}
	if(!(	pLee =			(BDCLEE)			GetProcAddress (*hDll, "BdcLee"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcLee\n");
			pLee =			(BDCLEE)			BdcLee;
	}
	if(!(	pDecodifica =	(BDCDECODIFICA)		GetProcAddress (*hDll, "BdcDecodifica"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcDecodifica\n");
			pDecodifica =	(BDCDECODIFICA)		BdcDecodifica;
	}
	if(!(	pParNumero =	(BDCPARNUMERO)		GetProcAddress (*hDll, "BdcParNumero"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcParNumero\n");
			pParNumero =	(BDCPARNUMERO)		BdcParNumero;
	}
	if(!(	pOpcNumero =	(BDCOPCNUMERO)		GetProcAddress (*hDll, "BdcOpcNumero"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcOpcNumero\n");
			pOpcNumero =	(BDCOPCNUMERO)		BdcOpcNumero;
	}
	if(!(	pParRotulo =	(BDCPARROTULO)		GetProcAddress (*hDll, "BdcParRotulo"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcParRotulo\n");
			pParRotulo =	(BDCPARROTULO)		BdcParRotulo;
	}
	if(!(	pOpcRotulo =	(BDCOPCROTULO)		GetProcAddress (*hDll, "BdcOpcRotulo"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcOpcRotulo\n");
			pOpcRotulo =	(BDCOPCROTULO)		BdcOpcRotulo;
	}
	if(!(	pValida =		(BDCVALIDA)			GetProcAddress (*hDll, "BdcValida"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcValida\n");
			pValida =		(BDCVALIDA)			BdcValida;
	}
	if(!(	pCalcula =		(BDCCALCULA)		GetProcAddress (*hDll, "BdcCalcula"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcCalcula\n");
			pCalcula =		(BDCCALCULA)		BdcCalcula;
	}
	if(!(	pValidos =		(BDCVALIDOS)		GetProcAddress (*hDll, "BdcValidos"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcValidos\n");
			pValidos =		(BDCVALIDOS)		BdcValidos;
	}
	if(!(	pCierra = 		(BDCCIERRA)			GetProcAddress (*hDll, "BdcCierra"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcCierra\n");
			pCierra =		(BDCCIERRA)			BdcCierra;
	}
	if(!(	pDesNumero =	(BDCDESNUMERO)		GetProcAddress (*hDll, "BdcDesNumero"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcDesNumero\n");
			pDesNumero =	(BDCDESNUMERO)		BdcDesNumero;
	}
	if(!(	pDesCodigo =	(BDCDESCODIGO)		GetProcAddress (*hDll, "BdcDesCodigo"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcDesCodigo\n");
			pDesCodigo =	(BDCDESCODIGO)		BdcDesCodigo;
	}
	if(!(	pRendimiento =	(BDCRENDIMIENTO)	GetProcAddress (*hDll, "BdcRendimiento"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcRendimiento\n");
			pRendimiento =	(BDCRENDIMIENTO)	BdcRendimiento;
	}
	if(!(	pPrecio =		(BDCPRECIO)			GetProcAddress (*hDll, "BdcPrecio"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcPrecio\n");
			pPrecio =		(BDCPRECIO)			BdcPrecio;
	}
	if(!(	pCodigo =		(BDCCODIGO)			GetProcAddress (*hDll, "BdcCodigo"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcCodigo\n");
			pCodigo =		(BDCCODIGO)			BdcPrecio;
	}
	if(!(	pUnidad =		(BDCUNIDAD)			GetProcAddress (*hDll, "BdcUnidad"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcUnidad\n");
			pUnidad =		(BDCUNIDAD)			BdcUnidad;
	}
	if(!(	pResumen =		(BDCRESUMEN)		GetProcAddress (*hDll, "BdcResumen"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcResumen\n");
			pResumen =		(BDCRESUMEN)		BdcResumen;
	}
	if(!(	pTexto =		(BDCTEXTO)			GetProcAddress (*hDll, "BdcTexto"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcTexto\n");
			pTexto =		(BDCTEXTO)			BdcTexto;
	}
	if(!(	pPliego =		(BDCPLIEGO)			GetProcAddress (*hDll, "BdcPliego"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcPliego\n");
			pPliego =		(BDCPLIEGO)			BdcPliego;
	}
	if(!(	pCodParrafo =	(BDCCODPARRAFO)		GetProcAddress (*hDll, "BdcCodParrafo"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcCodParrafo\n");
			pCodParrafo =	(BDCCODPARRAFO)		BdcCodParrafo;
	}
	if(!(	pTexParrafo =	(BDCTEXPARRAFO)		GetProcAddress (*hDll, "BdcTexParrafo"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcTexParrafo\n");
			pTexParrafo =	(BDCTEXPARRAFO)		BdcTexParrafo;
	}
	if(!(	pComentario =	(BDCCOMENTARIO)		GetProcAddress (*hDll, "BdcComentario"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcComentario\n");
			pComentario =	(BDCCOMENTARIO)		BdcComentario;
	}
	if(!(	pClaves =		(BDCCLAVES)			GetProcAddress (*hDll, "BdcClaves"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcClaves\n");
			pClaves =		(BDCCLAVES)			BdcClaves;
	}
	if(!(	pError =		(BDCERROR)			GetProcAddress (*hDll, "BdcError"))) {
			HayError=TRUE;
			strcat (err,  "\tBdcError\n");
			pError =		(BDCERROR)			BdcError;
	}

	if (HayError)
		*Err=err;
	else
		*Err = "";
	return TRUE;
}

BOOL
CierraDll (
HMODULE	hDll,
char	**Err )
{
	if (hDll) {
		if ( !FreeLibrary (hDll) ) {
			*Err = "ERROR AL CERRAR LA LIBRERIA";
			return FALSE;
		} else {
			*Err = "";
			return TRUE;
		}
	} else {
		*Err = "NO HAY LIBRERIA QUE CERRAR";
		return FALSE;
	}
}

BOOL
ChequeaError (
HANDLE	Precio,
FILE	*f,
BOOL	EsGlobal )
{
	const char	*MensajeError;
	BOOL		CodigoError;

	CodigoError= EsGlobal ? pGloError (&MensajeError) : pError (Precio, &MensajeError);

	if (CodigoError ==BDCERR_CORRECTO)
		return TRUE;
	if (MensajeError[0]) {
		fprintf (f,"ERROR: %s\n",MensajeError);
		return TRUE;
	}
	if (CodigoError & BDCERR_BASE_DATOS)
		fprintf (f,"ERROR: Error no especificado por la Base de Datos\n");
	if (CodigoError & BDCERR_PARAMETRO)
		fprintf (f,"ERROR: El parámetro no existe\n");
	if (CodigoError & BDCERR_OPCION)
		fprintf (f,"ERROR: La opción no existe\n");
	if (CodigoError & BDCERR_MAX_OPCIONES)
		fprintf (f,"ERROR: Se alcanzó el máximo número de opciones (62)\n");
	if (CodigoError & BDCERR_NO_LEIDO)
		fprintf (f,"ERROR: La familia paramétrica no fue leída\n");
	if (CodigoError & BDCERR_NO_CALCULADO)
		fprintf (f,"ERROR: El derivado paramétrico no fue calculado\n");
	if (CodigoError & BDCERR_DESCOMPOSICION)
		fprintf (f,"ERROR: No existe un elemento de la descomposición\n");
	if (CodigoError & BDCERR_SIN_CODIGO)
		fprintf (f,"ERROR: El concepto no tiene código definido\n");
	if (CodigoError & BDCERR_SIN_MEMORIA)
		fprintf (f,"ERROR: Memoria insuficiente\n");
	if (CodigoError & BDCERR_CONCEPTO_NULO)
		fprintf (f,"ERROR: El concepto es erróneo\n");

	if (CodigoError & 0xFFFFF800)
		fprintf (f,"ERROR: El código de error %#x no está recogido en el formato\n", (CodigoError & 0xFFFFF800));
	return FALSE;
}

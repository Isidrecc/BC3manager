/*	FORMATO DE INTERCAMBIO ESTÁNDAR DE PARAMÉTRICOS EN DLL	*/
/*	FIEBDC-3/98 */

#include <windows.h>

#ifndef FIEBDC_H
#define FIEBDC_H

#ifdef BASE /* definido si se desea construir la DLL */

/****************************************************************************/
/*	PARTE DEL ARCHIVO NECESARIA PARA LOS DESARROLLADORES DE BASE DE DATOS	*/
/****************************************************************************/

/****************************************************************************/
/*	MACROS DEPENDIENTES DEL COMPILADOR */
#if defined (__BORLANDC__)	/* Borland C++ */
#ifdef __WIN32__
#define EXPORTA FAR _export
#else
#define EXPORTA huge _export
#endif /*__WIN32__*/

#elif defined (_MSC_VER)	/* Microsoft C */
#ifdef _WIN32
#define EXPORTA __stdcall
#else
#define EXPORTA FAR PASCAL
#endif /*_WIN32*/

#else						/* Otros       */
#define EXPORTA
#endif

#ifdef __cplusplus
extern "C" {
#endif

/*	0 FUNCIONES GENERALES	*************************************************/
LONG	EXPORTA BdcCodificacion		(VOID);
LONG	EXPORTA BdcTipoPliego		(VOID);

/*	1 FUNCIONES REFERENTES AL PARAMÉTRICO GLOBAL	*************************/
/*	1.1 Accesibles en cualquier momento */
/*	1.1.1 Obtención de sus parámetros */
LONG	EXPORTA BdcGloParNumero 	(VOID);
LONG	EXPORTA BdcGloOpcNumero 	(LONG par);
LPCSTR	EXPORTA BdcGloParRotulo 	(LONG par);
LPCSTR	EXPORTA BdcGloOpcRotulo 	(LONG par, LONG opc);
/*	2.1.3 Mensajes / códigos de error */
LONG	EXPORTA BdcGloError			(LPCSTR *err);
/*	1.1.2 Asignación de opciones a los parámetros */
BOOL	EXPORTA BdcGloCalcula		(LPLONG opcl);

/*	2 FUNCIONES REFERENTES AL RESTO DE PARAMÉTRICOS	***********************/
/*	2.1 Accesibles en cualquier momento */
/*	2.1.1 Lectura de un concepto paramétrico */
HANDLE	EXPORTA BdcLee				(LPCSTR cod);
/*	2.1.2 Lectura de un concepto paramétrico a partir del código del derivado */
HANDLE	EXPORTA BdcDecodifica		(LPCSTR cod, LPLONG opcl);
/*	2.1.3 Mensajes / códigos de error */
LONG	EXPORTA BdcError			(HANDLE h, LPCSTR *err);

/*	2.2 Accesibles después de BdcLee */
/*	2.2.1 Obtención de sus parámetros */
LONG	EXPORTA BdcParNumero 		(HANDLE h);
LONG	EXPORTA BdcOpcNumero 		(HANDLE h, LONG par);
LPCSTR	EXPORTA BdcParRotulo 		(HANDLE h, LONG par);
LPCSTR	EXPORTA BdcOpcRotulo 		(HANDLE h, LONG par, LONG opc);
/*	2.2.2 Obtención de un comentario */
LPCSTR	EXPORTA BdcComentario		(HANDLE h);
/*	2.2.3 Asignación de opciones de los parámetros y cálculo/chequeo del derivado */
BOOL	EXPORTA BdcValida			(HANDLE h, LPLONG opcl);
BOOL	EXPORTA BdcCalcula			(HANDLE h, LPLONG opcl);
LONG	EXPORTA BdcValidos			(HANDLE h, LPBYTE *opc);
/*	2.2.4 Liberación de memoria */
BOOL	EXPORTA BdcCierra			(HANDLE h);

/*	2.3 Accesibles después de BdcCalcula */
/*	2.3.1 Obtención del derivado paramétrico */
LONG	EXPORTA BdcDesNumero		(HANDLE h);
LPCSTR	EXPORTA BdcDesCodigo		(HANDLE h, LONG des);
BOOL	EXPORTA BdcRendimiento		(HANDLE h, LONG des, double FAR *ren);
BOOL	EXPORTA BdcPrecio			(HANDLE h, double FAR *pre);
LPCSTR	EXPORTA BdcCodigo			(HANDLE h);
LPCSTR	EXPORTA BdcResumen			(HANDLE h);
LPCSTR	EXPORTA BdcTexto			(HANDLE h);
LPCSTR	EXPORTA BdcPliego			(HANDLE h, LONG formato, LONG tipo, LPCSTR seccion, LPCSTR ambito);
LPCSTR	EXPORTA BdcCodParrafo		(HANDLE h, LONG tipo, LPCSTR seccion, LPCSTR ambito);
LPCSTR	EXPORTA BdcTexParrafo		(LONG formato, LPCSTR cod_parrafo);
LPCSTR	EXPORTA BdcClaves			(HANDLE h);
LPCSTR	EXPORTA BdcUnidad			(HANDLE h);

#ifdef __cplusplus
}
#endif

#else  /* BASE no definido */
/****************************************************************************/
/*	PARTE DEL ARCHIVO NECESARIA PARA LOS DESARROLLADORES DE PROGRAMAS		*/
/****************************************************************************/

/****************************************************************************/
/*	MACROS DEPENDIENTES DEL COMPILADOR */
#if defined (__BORLANDC__)	/* Borland C++ */
#ifdef __WIN32__
#define IMPORTA FAR _import
#else
#define IMPORTA huge _import
#endif /*__WIN32__*/

#elif defined (_MSC_VER)	/* Microsoft C */
#ifdef _WIN32
#define IMPORTA __stdcall
#else
#define IMPORTA FAR PASCAL
#endif /*_WIN32*/

#else						/* Otros       */
#define IMPORTA
#endif

/*	FUNCIONES GENERALES	*****************************************************/
typedef LONG	(IMPORTA * BDCCODIFICACION)	(VOID);
typedef LONG	(IMPORTA * BDCTIPOPLIEGO)	(VOID);

/*	FUNCIONES REFERENTES AL PARAMÉTRICO GLOBAL	*****************************/
typedef LONG	(IMPORTA * BDCGLOPARNUMERO)	(VOID);
typedef LONG	(IMPORTA * BDCGLOOPCNUMERO)	(LONG par);
typedef LPCSTR	(IMPORTA * BDCGLOPARROTULO)	(LONG par);
typedef LPCSTR	(IMPORTA * BDCGLOOPCROTULO)	(LONG par, LONG opc);
typedef LONG	(IMPORTA * BDCGLOERROR)		(LPCSTR *err);
typedef BOOL	(IMPORTA * BDCGLOCALCULA)	(LPLONG opcl);

/*	FUNCIONES REFERENTES AL RESTO DE PARAMÉTRICOS	*************************/
typedef HANDLE	(IMPORTA * BDCLEE)			(LPCSTR cod);
typedef HANDLE	(IMPORTA * BDCDECODIFICA)	(LPCSTR cod, LPLONG opcl);
typedef LONG	(IMPORTA * BDCERROR)		(HANDLE h, LPCSTR *err);
typedef LONG	(IMPORTA * BDCPARNUMERO)	(HANDLE h);
typedef LONG	(IMPORTA * BDCOPCNUMERO)	(HANDLE h, LONG par);
typedef LPCSTR	(IMPORTA * BDCPARROTULO)	(HANDLE h, LONG par);
typedef LPCSTR	(IMPORTA * BDCOPCROTULO)	(HANDLE h, LONG par, LONG opc);
typedef LPCSTR	(IMPORTA * BDCCOMENTARIO)	(HANDLE h);
typedef BOOL	(IMPORTA * BDCVALIDA)		(HANDLE h, LPLONG opcl);
typedef BOOL	(IMPORTA * BDCCALCULA)		(HANDLE h, LPLONG opcl);
typedef LONG	(IMPORTA * BDCVALIDOS)		(HANDLE h, LPBYTE *opc);
typedef BOOL	(IMPORTA * BDCCIERRA)		(HANDLE h);
typedef LONG	(IMPORTA * BDCDESNUMERO)	(HANDLE h);
typedef LPCSTR	(IMPORTA * BDCDESCODIGO)	(HANDLE h, LONG des);
typedef BOOL	(IMPORTA * BDCRENDIMIENTO)	(HANDLE h, LONG des, double FAR *ren);
typedef BOOL	(IMPORTA * BDCPRECIO)		(HANDLE h, double FAR *pre);
typedef LPCSTR	(IMPORTA * BDCCODIGO)		(HANDLE h);
typedef LPCSTR	(IMPORTA * BDCRESUMEN)		(HANDLE h);
typedef LPCSTR	(IMPORTA * BDCTEXTO)		(HANDLE h);
typedef LPCSTR	(IMPORTA * BDCPLIEGO)		(HANDLE h, LONG formato, LONG tipo, LPCSTR seccion, LPCSTR ambito);
typedef LPCSTR	(IMPORTA * BDCCODPARRAFO)	(HANDLE h, LONG tipo, LPCSTR seccion, LPCSTR ambito);
typedef LPCSTR	(IMPORTA * BDCTEXPARRAFO)	(LONG formato, LPCSTR cod_parrafo);
typedef LPCSTR	(IMPORTA * BDCCLAVES)		(HANDLE h);
typedef LPCSTR	(IMPORTA * BDCUNIDAD)		(HANDLE h);

#endif /* de #ifdef BASE */

/****************************************************************************/
/*	PARTE COMÚN DEL ARCHIVO: CÓDIGOS DE LOS MENSAJES DE ERROR				*/
/*	SE ALMACENAN COMO BITS DE UN LONG, DE MANERA QUE EXISTAN HASTA 32		*/
/****************************************************************************/

#define BDCERR_CORRECTO			0x000000	/* No hay error */
#define BDCERR_BASE_DATOS		0x000001	/* Existe un mensaje de error definido por el redactor de la base*/
#define BDCERR_PARAMETRO		0x000002	/* Se pasó a BdcCalcula o BdcGloCalcula un parámetro inexistente */
#define BDCERR_OPCION			0x000004	/* Se pasó a BdcCalcula o BdcGloCalcula una opción inexistente */
#define BDCERR_MAX_OPCIONES		0x000008	/* Se definieron más de 62 opciones */
#define BDCERR_NO_LEIDO			0x000010	/* Se intentó calcular un precio sin leer */
#define BDCERR_NO_CALCULADO		0x000020	/* Se intentó acceder a datos de un derivado no calculado */
#define BDCERR_DESCOMPOSICION	0x000040	/* Se intentó acceder a un ele. de la descomposición inexistente */
#define BDCERR_SIN_CODIGO		0x000080	/* No existe código definido */
#define BDCERR_SIN_MEMORIA		0x000100	/* Memoria insuficiente */
#define BDCERR_CONCEPTO_NULO	0x000200	/* Se pasó un HANDLE nulo */
#define	BDCERR_FMT_NO_SOPORTADO	0x000400	/* El formato de texto solicitado no está soportado por la BDC	*/

#define	BDCFMT_ASCII	0	/* Pliego en formato ASCII */
#define	BDCFMT_RTF		1	/* Pliego en formato RTF */
#define	BDCPLI_FAMILIA	0	/* Pliego de la familia */
#define	BDCPLI_DERIVADO	1	/* Pliego del derivado */

#endif /* FIEBDC_H */
